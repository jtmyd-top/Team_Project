# knowledge_project/views/message.py
"""私信 / 对话设置 / 屏蔽 / 用户搜索与公开资料相关视图"""
import json
import logging
import mimetypes
import os
import threading
from datetime import datetime, timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Count
from django.http import FileResponse, Http404, JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Note, ProfileLike
from ..realtime import push_user_event

logger = logging.getLogger(__name__)


def blocked_message_attachment_media_api(request, path=None):
    return HttpResponse('私信附件只能通过受控接口访问', status=403)

# 撤回时间窗口（秒）
RECALL_WINDOW_SECONDS = 120

# 每天主动发起新对话（陌生人）的免验证配额，超过后必须通过 Turnstile
NEW_CONV_DAILY_LIMIT = 5
# 同一对话的新私信邮件节流窗口（秒）
EMAIL_NOTIFY_WINDOW_SECONDS = 15 * 60
MESSAGE_PURGE_DELAY_DAYS = 7
MESSAGE_ATTACHMENT_MAX_COUNT = 6
MESSAGE_IMAGE_MAX_SIZE = 10 * 1024 * 1024
MESSAGE_AUDIO_MAX_SIZE = 12 * 1024 * 1024
MESSAGE_VIDEO_MAX_SIZE = 120 * 1024 * 1024
MESSAGE_FILE_MAX_SIZE = 25 * 1024 * 1024
MESSAGE_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MESSAGE_AUDIO_MIME_TYPES = {'audio/webm', 'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/x-wav'}
MESSAGE_VIDEO_MIME_TYPES = {'video/mp4', 'video/webm', 'video/quicktime'}
MESSAGE_FILE_MIME_TYPES = {
    'application/pdf',
    'application/zip',
    'application/x-zip-compressed',
    'text/plain',
    'text/markdown',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def _get_avatar_url(user):
    try:
        if user.profile.avatar:
            return user.profile.avatar.url
    except Exception:
        pass
    return '/static/img/default-avatar.png'


def _get_settings(user, peer):
    """获取或创建 user 对 peer 的会话设置"""
    from ..models import ConversationSettings
    settings, _ = ConversationSettings.objects.get_or_create(user=user, peer=peer)
    return settings


def _server_error_response(log_message, exc, public_message='服务器错误'):
    logger.error("%s: %s", log_message, exc, exc_info=True)
    return JsonResponse({'error': public_message}, status=500)


def _message_has_report_history(message):
    if message.was_reported:
        return True
    if message.reports.exists():
        return True
    return message.attachments.filter(Q(was_reported=True) | Q(reports__isnull=False)).exists()


def _message_has_blocking_dependencies(message):
    # 引用/转发目前以纯文本形式保存，没有外键依赖。后续如果持久化 reply_to/forward_from，
    # 这里应追加 exists() 检查，避免被引用源被物理删除。
    return False


def _message_can_be_scheduled_for_purge(message):
    if not (message.deleted_for_sender and message.deleted_for_recipient):
        return False
    if message.is_recalled or message.was_reported:
        return False
    if _message_has_report_history(message):
        return False
    if _message_has_blocking_dependencies(message):
        return False
    return True


def _refresh_message_purge_schedule(message):
    if _message_can_be_scheduled_for_purge(message):
        if not message.pending_purge_at:
            message.pending_purge_at = timezone.now() + timedelta(days=MESSAGE_PURGE_DELAY_DAYS)
            message.save(update_fields=['pending_purge_at'])
        return True
    if message.pending_purge_at:
        message.pending_purge_at = None
        message.save(update_fields=['pending_purge_at'])
    return False


def _refresh_purge_schedule_for_messages(messages):
    scheduled_ids = []
    for message in messages:
        if _refresh_message_purge_schedule(message):
            scheduled_ids.append(message.id)
    return scheduled_ids


def _push_new_message_events(message):
    push_user_event(message.sender_id, {
        'type': 'new_message',
        'message': _message_payload(message, viewer=message.sender),
        'peer_id': message.recipient_id,
    })
    push_user_event(message.recipient_id, {
        'type': 'new_message',
        'message': _message_payload(message, viewer=message.recipient),
        'peer_id': message.sender_id,
    })


def _push_message_read_event(target_user_id, peer_id, message_ids, reader_id):
    if not message_ids:
        return
    push_user_event(target_user_id, {
        'type': 'message_read',
        'message_ids': message_ids,
        'reader_id': reader_id,
        'peer_id': peer_id,
    })


def _push_message_recalled_event(message):
    push_user_event(message.sender_id, {
        'type': 'message_recalled',
        'message_id': message.id,
        'peer_id': message.recipient_id,
    })
    push_user_event(message.recipient_id, {
        'type': 'message_recalled',
        'message_id': message.id,
        'peer_id': message.sender_id,
    })


def _visible_messages_qs(viewer, peer, viewer_settings=None):
    """返回在 viewer 视角下可见的 viewer<->peer 消息 queryset（按时间升序）"""
    from ..models import Message
    qs = Message.objects.filter(
        (Q(sender=viewer) & Q(recipient=peer)) |
        (Q(sender=peer) & Q(recipient=viewer))
    ).exclude(is_recalled=True)

    # 排除各自已删除的
    qs = qs.exclude(Q(sender=viewer) & Q(deleted_for_sender=True))
    qs = qs.exclude(Q(recipient=viewer) & Q(deleted_for_recipient=True))

    # 过滤清空时间戳之前
    if viewer_settings and viewer_settings.cleared_before:
        qs = qs.filter(created_at__gt=viewer_settings.cleared_before)

    return qs.order_by('created_at')


def _apply_disappearing(viewer, peer, viewer_settings=None, peer_settings=None):
    """懒惰清理：任一方开启阅后即焚且消息已读超过 TTL 即销毁。

    - 读取 viewer / peer 双方的 ConversationSettings
    - 任一方 disappearing_enabled=True 即生效，TTL 取所有开启方中的最短值
    - TTL=0 表示「阅读后立即」—— 所有已读消息全部立即销毁
    - 销毁方式：is_recalled=True（双方视图都不可见）
    """
    from ..models import ConversationSettings, Message

    if viewer_settings is None:
        viewer_settings = ConversationSettings.objects.filter(user=viewer, peer=peer).first()
    if peer_settings is None:
        peer_settings = ConversationSettings.objects.filter(user=peer, peer=viewer).first()

    ttls = []
    if viewer_settings and viewer_settings.disappearing_enabled:
        ttls.append(max(viewer_settings.disappearing_ttl_seconds or 0, 0))
    if peer_settings and peer_settings.disappearing_enabled:
        ttls.append(max(peer_settings.disappearing_ttl_seconds or 0, 0))

    if not ttls:
        return

    ttl = min(ttls)
    base_qs = Message.objects.filter(
        (Q(sender=viewer) & Q(recipient=peer)) |
        (Q(sender=peer) & Q(recipient=viewer)),
        is_read=True,
        is_recalled=False,
        read_at__isnull=False,
    )
    if ttl > 0:
        base_qs = base_qs.filter(read_at__lt=timezone.now() - timedelta(seconds=ttl))
    base_qs.update(is_recalled=True, recalled_at=timezone.now())


def _count_unread(user, peer, viewer_settings=None):
    """计算 user 视角下 peer → user 的未读数，遵循清空时间戳与 force_unread"""
    from ..models import Message
    qs = Message.objects.filter(
        sender=peer, recipient=user,
        is_read=False, is_recalled=False, deleted_for_recipient=False,
    )
    if viewer_settings and viewer_settings.cleared_before:
        qs = qs.filter(created_at__gt=viewer_settings.cleared_before)
    count = qs.count()
    if count == 0 and viewer_settings and viewer_settings.force_unread:
        return 1
    return count


def _message_payload(msg, viewer=None):
    return {
        'id': msg.id,
        'sender': msg.sender.username,
        'sender_id': msg.sender_id,
        'sender_avatar': _get_avatar_url(msg.sender),
        'recipient': msg.recipient.username,
        'recipient_id': msg.recipient_id,
        'content': msg.content,
        'created_at': msg.created_at.isoformat(),
        'is_read': msg.is_read,
        'read_at': msg.read_at.isoformat() if msg.read_at else None,
        'is_own': (viewer is not None and viewer.id == msg.sender_id),
        'attachments': [_attachment_payload(a) for a in msg.attachments.all()],
    }


def _attachment_payload(attachment):
    return {
        'id': attachment.id,
        'type': attachment.attachment_type,
        'name': attachment.original_name,
        'mime_type': attachment.mime_type,
        'size': attachment.size,
        'url': f'/api/messages/attachments/{attachment.id}/file/',
    }


def _message_preview(msg):
    if msg.content:
        return msg.content
    return _attachment_preview(msg.attachments.first())


def _attachment_preview(first_attachment):
    if not first_attachment:
        return ''
    if first_attachment.attachment_type == 'image':
        return '[图片]'
    if first_attachment.attachment_type == 'audio':
        return '[语音]'
    if first_attachment.attachment_type == 'video':
        return '[视频]'
    return f'[文件] {first_attachment.original_name}'


def _serve_attachment_file(attachment, disposition=None):
    try:
        file_path = os.path.normpath(attachment.file.path)
        media_root = os.path.normpath(settings.MEDIA_ROOT)
        if file_path != media_root and not file_path.startswith(media_root + os.sep):
            raise Http404
        response = FileResponse(open(file_path, 'rb'), content_type=attachment.mime_type or 'application/octet-stream')
    except (FileNotFoundError, ValueError):
        raise Http404

    if disposition is None:
        disposition = 'inline' if attachment.attachment_type in ('image', 'audio', 'video') else 'attachment'
    fallback_name = attachment.original_name.encode('ascii', 'ignore').decode('ascii') or 'attachment'
    fallback_name = fallback_name.replace('"', '')
    response['Content-Disposition'] = (
        f'{disposition}; filename="{fallback_name}"; filename*=UTF-8\'\'{quote(attachment.original_name)}'
    )
    return response


def _delete_attachment_files(attachments):
    for attachment in attachments:
        if attachment.file:
            try:
                attachment.file.delete(save=False)
            except Exception as exc:
                logger.warning("删除私信附件文件失败: attachment=%s, error=%s", attachment.id, exc, exc_info=True)
        attachment.delete()


def _normalize_attachment_ids(raw_ids):
    if raw_ids in (None, ''):
        return []
    if not isinstance(raw_ids, list):
        raise ValueError('attachment_ids must be a list')
    ids = []
    seen = set()
    for raw_id in raw_ids:
        try:
            attachment_id = int(raw_id)
        except (TypeError, ValueError):
            raise ValueError('attachment_ids contains invalid id')
        if attachment_id <= 0 or attachment_id in seen:
            continue
        seen.add(attachment_id)
        ids.append(attachment_id)
    if len(ids) > MESSAGE_ATTACHMENT_MAX_COUNT:
        raise ValueError(f'一次最多发送 {MESSAGE_ATTACHMENT_MAX_COUNT} 个附件')
    return ids


def _is_new_conversation(sender, recipient):
    """判断 sender -> recipient 是否属于"新对话"

    没有历史往来消息（任意方向、不计撤回/自删）即视为新对话。
    """
    from ..models import Message
    return not Message.objects.filter(
        (Q(sender=sender) & Q(recipient=recipient)) |
        (Q(sender=recipient) & Q(recipient=sender))
    ).exists()


def _today_new_conv_count(user):
    """当日（本地日）该用户主动发起的新对话次数"""
    from ..models import NewConversationQuotaLog
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return NewConversationQuotaLog.objects.filter(
        user=user, created_at__gte=start
    ).count()


def _body_string(data, field_name, default=''):
    value = data.get(field_name, default)
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    logger.warning("Invalid request field type for %s: %s", field_name, type(value).__name__)
    raise ValueError(f"{field_name} must be a string")


def _validate_send_message_input(data):
    recipient_id = data.get('recipient_id')
    content = _body_string(data, 'content')
    attachment_ids = _normalize_attachment_ids(data.get('attachment_ids'))
    if not recipient_id or (not content and not attachment_ids):
        raise ValueError('缺少必需参数')
    if len(content) > 5000:
        raise ValueError('消息内容不能超过5000字')
    return recipient_id, content, attachment_ids


def _load_message_attachments(user, attachment_ids):
    if not attachment_ids:
        return []
    from ..models import MessageAttachment

    attachments = list(
        MessageAttachment.objects.filter(
            id__in=attachment_ids,
            uploader=user,
            message__isnull=True,
        )
    )
    if len(attachments) != len(attachment_ids):
        raise ValueError('附件不存在、已发送或无权使用')
    return attachments


def _check_send_permissions(sender, recipient):
    from ..models import MessagePreference, UserBlocklist, UserFollow

    if recipient == sender:
        return JsonResponse({'error': '不能给自己发送私信'}, status=400), None

    if UserBlocklist.objects.filter(user=recipient, blocked_user=sender).exists():
        return JsonResponse({'error': '无法向此用户发送私信'}, status=403), None

    pref, _ = MessagePreference.objects.get_or_create(user=recipient)
    if UserBlocklist.objects.filter(user=sender, blocked_user=recipient).exists():
        return JsonResponse({'error': '你已屏蔽此用户，解除屏蔽后才能发送私信'}, status=403), None
    if not pref.allow_messages or pref.message_mode == 'disabled':
        return JsonResponse({'error': '此用户未开启私信功能'}, status=403), None

    if pref.message_mode == 'followers_only':
        if not UserFollow.objects.filter(follower=sender, following=recipient).exists():
            return JsonResponse({'error': '对方仅接收其关注者的私信'}, status=403), None
    elif pref.message_mode == 'following_only':
        if not UserFollow.objects.filter(follower=recipient, following=sender).exists():
            return JsonResponse({'error': '对方仅接收其已关注用户的私信'}, status=403), None

    return None, pref


def _verify_new_conversation_quota(request, data, recipient):
    is_new_conv = _is_new_conversation(request.user, recipient)
    if not is_new_conv:
        return False

    quota_used = _today_new_conv_count(request.user)
    if quota_used < NEW_CONV_DAILY_LIMIT:
        return False

    raw_turnstile_token = data.get('turnstile_token')
    if raw_turnstile_token in (None, ''):
        raise PermissionError('turnstile_required')
    if not isinstance(raw_turnstile_token, str):
        raise ValueError('人机验证参数无效，请重试')
    turnstile_token = raw_turnstile_token.strip()
    if not turnstile_token:
        raise PermissionError('turnstile_required')

    from ..utils.turnstile import verify_turnstile_token
    from ..utils.request_utils import get_client_ip
    if not verify_turnstile_token(turnstile_token, get_client_ip(request)):
        raise PermissionError('turnstile_failed')
    return True


def _update_conversation_state(sender, recipient):
    recipient_settings = _get_settings(recipient, sender)
    recipient_settings.force_unread = False
    if recipient_settings.is_archived:
        recipient_settings.is_archived = False
        recipient_settings.archived_at = None
    recipient_settings.save()

    sender_settings = _get_settings(sender, recipient)
    sender_settings.last_read_at = timezone.now()
    sender_settings.force_unread = False
    sender_settings.save()
    return sender_settings


def _maybe_send_new_message_email(sender, recipient, content):
    """聚合邮件通知：同一接收者 15 分钟内至多一封。

    尊重 MessagePreference.notify_new_message 开关；失败只记日志，不影响主流程。
    """
    try:
        from ..models import MessagePreference
        pref, _ = MessagePreference.objects.get_or_create(user=recipient)
        if not pref.notify_new_message:
            return
        if not recipient.email:
            return
        now = timezone.now()
        cutoff = now - timedelta(seconds=EMAIL_NOTIFY_WINDOW_SECONDS)
        claimed = MessagePreference.objects.filter(
            Q(last_email_notified_at__isnull=True) | Q(last_email_notified_at__lte=cutoff),
            pk=pref.pk,
            notify_new_message=True,
        ).update(last_email_notified_at=now)
        if not claimed:
            return

        from ..utils.smart_email_sender import SmartEmailSender
        subject = f"你收到了来自 {sender.username} 的新私信"
        snippet = (content or '').strip().replace('\n', ' ')
        if len(snippet) > 80:
            snippet = snippet[:77] + '...'
        body = (
            f"你好 {recipient.username}：\n\n"
            f"{sender.username} 刚刚给你发来了一条私信：\n\n"
            f"    {snippet}\n\n"
            f"登录后前往「私信」查看完整对话。\n\n"
            f"---\n"
            f"如不希望再收到此类通知，可在「设置 → 通知设置」中关闭新消息邮件提醒。"
        )

        def send_email_notification():
            success, method = SmartEmailSender().send_email(subject, body, [recipient.email])
            if not success:
                logger.warning("新私信邮件通知发送失败: recipient=%s", recipient.id)
            else:
                logger.info("新私信邮件通知已发送: recipient=%s, method=%s", recipient.id, method)

        threading.Thread(target=send_email_notification, daemon=True).start()
    except Exception as e:
        logger.warning("新私信邮件通知失败: %s", e, exc_info=True)


# ------------------------------------------------------------------
# 发送 / 获取 / 对话列表
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def send_message_api(request):
    """发送私信"""
    try:
        from ..models import Message, MessageAttachment, NewConversationQuotaLog

        data = json.loads(request.body)
        try:
            recipient_id, content, attachment_ids = _validate_send_message_input(data)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        recipient = get_object_or_404(User, id=recipient_id)
        permission_response, _ = _check_send_permissions(request.user, recipient)
        if permission_response is not None:
            return permission_response

        attachments = _load_message_attachments(request.user, attachment_ids)

        # 新对话限流：超出免验证配额时必须通过 Turnstile
        is_new_conv = _is_new_conversation(request.user, recipient)
        try:
            turnstile_passed = _verify_new_conversation_quota(request, data, recipient)
        except PermissionError as exc:
            if str(exc) == 'turnstile_failed':
                return JsonResponse({
                    'error': '人机验证失败，请重试',
                    'need_turnstile': True,
                }, status=403)
            quota_used = _today_new_conv_count(request.user)
            return JsonResponse({
                'error': '今日新对话数量已达上限，请完成人机验证',
                'need_turnstile': True,
                'quota_used': quota_used,
                'quota_limit': NEW_CONV_DAILY_LIMIT,
            }, status=429)

        with transaction.atomic():
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
            )
            if attachments:
                updated_count = MessageAttachment.objects.filter(
                    id__in=attachment_ids,
                    uploader=request.user,
                    message__isnull=True,
                ).update(message=message)
                if updated_count != len(attachment_ids):
                    raise ValueError('附件不存在、已发送或无权使用')

            # 记录新对话配额日志（总是记录，便于审计；限流字段标记是否走了 Turnstile）
            if is_new_conv:
                NewConversationQuotaLog.objects.create(
                    user=request.user,
                    peer=recipient,
                    turnstile_passed=turnstile_passed,
                )

            sender_settings = _update_conversation_state(request.user, recipient)

            preview_for_email = content or _attachment_preview(attachments[0] if attachments else None)
            transaction.on_commit(
                lambda: _maybe_send_new_message_email(request.user, recipient, preview_for_email)
            )
            transaction.on_commit(lambda: _push_new_message_events(message))

        # 发送动作也触发一次阅后即焚清理（若发送者或对方有超 TTL 的旧已读消息）
        _apply_disappearing(request.user, recipient, sender_settings)

        return JsonResponse({
            'status': 'success',
            'message': _message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except IntegrityError as e:
        logger.warning("发送私信数据库冲突: %s", e, exc_info=True)
        return JsonResponse({'error': '请求冲突，请稍后重试'}, status=409)
    except Exception as e:
        return _server_error_response('发送私信错误', e)


@require_http_methods(["POST"])
@login_required
def upload_message_attachment_api(request):
    """上传私信附件。附件先归属于上传者，发送消息时再绑定。"""
    try:
        from ..models import MessageAttachment

        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'error': '没有找到上传的文件'}, status=400)

        original_name = os.path.basename(uploaded.name or 'attachment')[:255]
        mime_type = uploaded.content_type or mimetypes.guess_type(original_name)[0] or 'application/octet-stream'
        size = uploaded.size or 0
        is_image = mime_type in MESSAGE_IMAGE_MIME_TYPES
        is_audio = mime_type in MESSAGE_AUDIO_MIME_TYPES
        is_video = mime_type in MESSAGE_VIDEO_MIME_TYPES

        if is_image:
            if size > MESSAGE_IMAGE_MAX_SIZE:
                return JsonResponse({'error': '图片不能超过 10MB'}, status=400)
            attachment_type = 'image'
        elif is_audio:
            if size > MESSAGE_AUDIO_MAX_SIZE:
                return JsonResponse({'error': '语音不能超过 12MB'}, status=400)
            attachment_type = 'audio'
        elif is_video:
            if size > MESSAGE_VIDEO_MAX_SIZE:
                return JsonResponse({'error': '视频不能超过 120MB'}, status=400)
            attachment_type = 'video'
        elif mime_type in MESSAGE_FILE_MIME_TYPES:
            if size > MESSAGE_FILE_MAX_SIZE:
                return JsonResponse({'error': '文件不能超过 25MB'}, status=400)
            attachment_type = 'file'
        else:
            return JsonResponse({'error': '暂不支持该文件类型'}, status=400)

        attachment = MessageAttachment.objects.create(
            uploader=request.user,
            file=uploaded,
            original_name=original_name,
            attachment_type=attachment_type,
            mime_type=mime_type,
            size=size,
        )
        return JsonResponse({
            'status': 'success',
            'attachment': _attachment_payload(attachment),
        }, status=201)
    except Exception as e:
        logger.error(f"上传私信附件失败: {e}", exc_info=True)
        return JsonResponse({'error': '上传失败，请稍后重试'}, status=500)


@require_http_methods(["GET"])
@login_required
def message_attachment_file_api(request, attachment_id):
    """受控访问私信附件，仅会话双方或待发送附件上传者可访问。"""
    from ..models import MessageAttachment

    attachment = get_object_or_404(MessageAttachment.objects.select_related('message'), id=attachment_id)
    message = attachment.message
    if message is None:
        if attachment.uploader_id != request.user.id:
            return HttpResponse('无权访问此附件', status=403)
    elif request.user.id not in (message.sender_id, message.recipient_id) or not message.visible_to(request.user):
        return HttpResponse('无权访问此附件', status=403)

    return _serve_attachment_file(attachment)


@require_http_methods(["GET"])
@login_required
def review_reported_attachment(request, attachment_id):
    """仅允许管理员审查存在待处理举报工单的私信附件。"""
    from ..models import AttachmentReport, MessageAttachment

    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden('仅管理员可审查被举报附件')

    attachment = get_object_or_404(MessageAttachment.objects.select_related('message'), id=attachment_id)
    has_pending_report = AttachmentReport.objects.filter(
        attachment=attachment,
        status='pending'
    ).exists()
    if not has_pending_report:
        return HttpResponseForbidden('无查看权限或工单已结案')

    return _serve_attachment_file(attachment, disposition='inline')


@require_http_methods(["POST"])
@login_required
def report_message_attachment_api(request, attachment_id):
    """私信当事人举报指定附件，创建待处理附件举报工单。"""
    from ..models import AttachmentReport, MessageAttachment

    attachment = get_object_or_404(
        MessageAttachment.objects.select_related('message'),
        id=attachment_id
    )
    message = attachment.message
    if message is None or request.user.id not in (message.sender_id, message.recipient_id):
        return HttpResponseForbidden('只有私信参与者才能举报该附件')

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)

    reason = _body_string(data, 'reason', 'other')[:120]
    detail = _body_string(data, 'detail', '')[:1000]
    report, created = AttachmentReport.objects.get_or_create(
        attachment=attachment,
        reporter=request.user,
        status='pending',
        defaults={
            'reason': reason,
            'detail': detail,
        }
    )
    if not attachment.was_reported:
        attachment.was_reported = True
        attachment.save(update_fields=['was_reported'])
    if message and not message.was_reported:
        message.was_reported = True
        message.pending_purge_at = None
        message.save(update_fields=['was_reported', 'pending_purge_at'])

    return JsonResponse({
        'status': 'success',
        'message': '附件举报已提交，我们会尽快处理',
        'report_id': report.id,
        'created': created,
    }, status=201 if created else 200)


@require_http_methods(["GET"])
@login_required
def get_messages_api(request):
    """获取与指定用户的对话消息（支持 ?q=关键字 搜索）"""
    try:
        other_user_id = request.GET.get('user_id')
        query = request.GET.get('q', '').strip()
        if not other_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)

        other_user = get_object_or_404(User, id=other_user_id)
        viewer_settings = _get_settings(request.user, other_user)

        # 第 1 次清理：销毁打开前就已过期的已读消息（不让用户再次看到）
        _apply_disappearing(request.user, other_user, viewer_settings)

        messages_qs = _visible_messages_qs(request.user, other_user, viewer_settings)
        if query:
            messages_qs = messages_qs.filter(content__icontains=query)

        # 强制求值为列表，后续的 is_read / is_recalled 更新不影响这份快照
        messages_list = list(messages_qs)
        unread_ids = [m.id for m in messages_list if m.sender_id == other_user.id and not m.is_read]

        # 标记接收到的消息为已读（仅对 recipient=viewer 的未读消息）
        from ..models import Message
        Message.objects.filter(
            recipient=request.user, sender=other_user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        # 更新 viewer 的 last_read_at 并清除 force_unread
        viewer_settings.last_read_at = timezone.now()
        viewer_settings.force_unread = False
        viewer_settings.save()
        _push_message_read_event(other_user.id, request.user.id, unread_ids, request.user.id)

        # 第 2 次清理：若任一方 TTL=0，则本次刚标记已读的消息立即销毁（下次打开不可见）
        _apply_disappearing(request.user, other_user, viewer_settings)

        data = [_message_payload(m, viewer=request.user) for m in messages_list]
        return JsonResponse({
            'status': 'success',
            'messages': data,
            'other_user': {
                'id': other_user.id,
                'username': other_user.username,
                'avatar': _get_avatar_url(other_user),
            },
            'settings': _conversation_settings_payload(viewer_settings),
        })
    except Exception as e:
        return _server_error_response('获取私信列表错误', e)


def _conversation_settings_payload(cs):
    return {
        'is_pinned': cs.is_pinned,
        'pinned_at': cs.pinned_at.isoformat() if cs.pinned_at else None,
        'is_muted': cs.is_muted,
        'is_archived': cs.is_archived,
        'disappearing_enabled': cs.disappearing_enabled,
        'disappearing_ttl_seconds': cs.disappearing_ttl_seconds,
        'force_unread': cs.force_unread,
        'cleared_before': cs.cleared_before.isoformat() if cs.cleared_before else None,
    }


@require_http_methods(["GET"])
@login_required
def get_message_conversations_api(request):
    """对话列表，支持 scope=all|unread|archived|blocked"""
    try:
        from ..models import Message, ConversationSettings, UserBlocklist

        scope = request.GET.get('scope', 'all')

        # 已屏蔽 tab 直接返回屏蔽列表
        if scope == 'blocked':
            blocked = UserBlocklist.objects.filter(user=request.user).select_related('blocked_user')
            data = [
                {
                    'user_id': b.blocked_user.id,
                    'username': b.blocked_user.username,
                    'avatar': _get_avatar_url(b.blocked_user),
                    'is_blocked': True,
                    'blocked_at': b.created_at.isoformat() if b.created_at else None,
                    'reason': b.reason,
                }
                for b in blocked
            ]
            return JsonResponse({'status': 'success', 'conversations': data})

        # 查询所有涉及 viewer 的 peer 用户 id
        msgs = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).exclude(is_recalled=True).prefetch_related('attachments').order_by('-created_at')

        # 排除对自己已删除
        msgs = msgs.exclude(Q(sender=request.user) & Q(deleted_for_sender=True))
        msgs = msgs.exclude(Q(recipient=request.user) & Q(deleted_for_recipient=True))

        # 所有 peer 的最新一条消息
        seen_peers = set()
        ordered_peers = []
        for m in msgs:
            peer_id = m.recipient_id if m.sender_id == request.user.id else m.sender_id
            if peer_id in seen_peers:
                continue
            seen_peers.add(peer_id)
            ordered_peers.append((peer_id, m))

        peer_ids = [peer_id for peer_id, _ in ordered_peers]
        peer_map = User.objects.filter(id__in=peer_ids).select_related('profile').in_bulk()
        existing_settings = ConversationSettings.objects.filter(
            user=request.user,
            peer_id__in=peer_ids,
        )
        settings_map = {cs.peer_id: cs for cs in existing_settings}
        missing_settings = [
            ConversationSettings(user=request.user, peer_id=peer_id)
            for peer_id in peer_ids
            if peer_id in peer_map and peer_id not in settings_map
        ]
        if missing_settings:
            ConversationSettings.objects.bulk_create(missing_settings, ignore_conflicts=True)
            settings_map = {
                cs.peer_id: cs
                for cs in ConversationSettings.objects.filter(user=request.user, peer_id__in=peer_ids)
            }

        peer_settings_map = {
            cs.user_id: cs
            for cs in ConversationSettings.objects.filter(user_id__in=peer_ids, peer=request.user)
        }

        blocked_ids = set(
            UserBlocklist.objects.filter(user=request.user).values_list('blocked_user_id', flat=True)
        )

        unread_filter = Q()
        for peer_id in peer_ids:
            cs = settings_map.get(peer_id)
            peer_filter = Q(sender_id=peer_id)
            if cs and cs.cleared_before:
                peer_filter &= Q(created_at__gt=cs.cleared_before)
            unread_filter |= peer_filter
        if unread_filter:
            unread_map = {
                row['sender_id']: row['total']
                for row in Message.objects.filter(
                    unread_filter,
                    recipient=request.user,
                    is_read=False,
                    is_recalled=False,
                    deleted_for_recipient=False,
                ).values('sender_id').annotate(total=Count('id'))
            }
        else:
            unread_map = {}

        conversations = []
        for peer_id, last_msg in ordered_peers:
            peer = peer_map.get(peer_id)
            if peer is None:
                continue
            cs = settings_map[peer_id]
            peer_cs = peer_settings_map.get(peer_id)

            # 懒惰清理：任一方开启阅后即焚时，遍历到此对话就触发一次
            if cs.disappearing_enabled or (peer_cs and peer_cs.disappearing_enabled):
                _apply_disappearing(request.user, peer, cs, peer_cs)

            # 过滤 scope
            if scope == 'archived' and not cs.is_archived:
                continue
            if scope in ('all', 'unread') and cs.is_archived:
                continue  # 归档的对话不在其他 Tab 显示
            if peer_id in blocked_ids and scope != 'blocked':
                continue

            # 如果清空后没有新消息则不在列表里显示
            if cs.cleared_before and last_msg.created_at <= cs.cleared_before:
                continue

            unread = unread_map.get(peer_id, 0)
            if unread == 0 and cs.force_unread:
                unread = 1
            if scope == 'unread' and unread == 0:
                continue

            preview = _message_preview(last_msg)
            conversations.append({
                'user_id': peer.id,
                'username': peer.username,
                'avatar': _get_avatar_url(peer),
                'last_message': preview,
                'last_message_time': last_msg.created_at.isoformat(),
                'last_sender_id': last_msg.sender_id,
                'unread_count': unread,
                'is_pinned': cs.is_pinned,
                'pinned_at': cs.pinned_at.isoformat() if cs.pinned_at else None,
                'is_muted': cs.is_muted,
                'is_archived': cs.is_archived,
                'disappearing_enabled': cs.disappearing_enabled,
                'force_unread': cs.force_unread,
                'is_blocked': peer_id in blocked_ids,
            })

        # 排序：置顶在前（按 pinned_at 降序），其它按 last_message_time 降序
        conversations.sort(
            key=lambda c: (
                not c['is_pinned'],
                -(datetime.fromisoformat(c['pinned_at']).timestamp()
                  if c.get('pinned_at') else 0),
                -datetime.fromisoformat(c['last_message_time']).timestamp(),
            )
        )

        return JsonResponse({'status': 'success', 'conversations': conversations})
    except Exception as e:
        return _server_error_response('获取对话列表错误', e)


# ------------------------------------------------------------------
# 删除 / 撤回
# ------------------------------------------------------------------
@require_http_methods(["POST", "DELETE"])
@login_required
def delete_message_api(request, message_id):
    """删除单条消息
    body: {scope: 'self' | 'both'}
    - self: 仅对自己隐藏（任意一方可操作）
    - both: 发送者 2 分钟内可撤回（双方都不可见）
    """
    try:
        from ..models import Message
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        scope = data.get('scope', 'self')

        msg = get_object_or_404(Message, id=message_id)

        if request.user.id not in (msg.sender_id, msg.recipient_id):
            return JsonResponse({'error': '无权操作此消息'}, status=403)

        if scope == 'both':
            if msg.sender_id != request.user.id:
                return JsonResponse({'error': '只有发送者可以撤回'}, status=403)
            if msg.created_at < timezone.now() - timedelta(seconds=RECALL_WINDOW_SECONDS):
                return JsonResponse({
                    'error': f'发送超过 {RECALL_WINDOW_SECONDS // 60} 分钟的消息不能撤回'
                }, status=403)
            with transaction.atomic():
                msg.is_recalled = True
                msg.recalled_at = timezone.now()
                msg.pending_purge_at = None
                msg.save(update_fields=['is_recalled', 'recalled_at', 'pending_purge_at'])
                transaction.on_commit(lambda: _push_message_recalled_event(msg))
            return JsonResponse({'status': 'success', 'scope': 'both'})

        # scope == self
        if request.user.id == msg.sender_id:
            msg.deleted_for_sender = True
        if request.user.id == msg.recipient_id:
            msg.deleted_for_recipient = True
        msg.save(update_fields=['deleted_for_sender', 'deleted_for_recipient'])
        scheduled = _refresh_message_purge_schedule(msg)
        return JsonResponse({'status': 'success', 'scope': 'self', 'scheduled_for_purge': scheduled})
    except Exception as e:
        return _server_error_response('删除消息错误', e)


@require_http_methods(["POST"])
@login_required
def bulk_delete_messages_api(request):
    """批量删除消息，仅在当前用户视图中隐藏。双方都删除后进入 7 天延迟物理清理队列。"""
    try:
        from ..models import Message
        data = json.loads(request.body)
        raw_ids = data.get('message_ids') or []
        if not isinstance(raw_ids, list):
            return JsonResponse({'error': 'message_ids 必须是数组'}, status=400)

        message_ids = []
        for value in raw_ids[:200]:
            try:
                message_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        message_ids = list(dict.fromkeys(message_ids))
        if not message_ids:
            return JsonResponse({'error': '请选择要删除的消息'}, status=400)

        messages = list(
            Message.objects.filter(id__in=message_ids)
            .filter(Q(sender=request.user) | Q(recipient=request.user))
            .prefetch_related('attachments__reports', 'reports')
        )
        found_ids = {message.id for message in messages}
        if len(found_ids) != len(message_ids):
            return JsonResponse({'error': '部分消息不存在或无权删除'}, status=403)

        sender_ids = [message.id for message in messages if message.sender_id == request.user.id]
        recipient_ids = [message.id for message in messages if message.recipient_id == request.user.id]

        with transaction.atomic():
            if sender_ids:
                Message.objects.filter(id__in=sender_ids).update(deleted_for_sender=True)
            if recipient_ids:
                Message.objects.filter(id__in=recipient_ids).update(deleted_for_recipient=True)

            refreshed = list(
                Message.objects.filter(id__in=message_ids).prefetch_related('attachments__reports', 'reports')
            )
            scheduled_ids = _refresh_purge_schedule_for_messages(refreshed)

        return JsonResponse({
            'status': 'success',
            'deleted_ids': message_ids,
            'scheduled_for_purge_ids': scheduled_ids,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('批量删除私信错误', e)


@require_http_methods(["POST"])
@login_required
def clear_conversation_api(request):
    """清空与某用户的对话（仅对自己）"""
    try:
        data = json.loads(request.body)
        peer_id = data.get('user_id')
        if not peer_id:
            return JsonResponse({'error': '缺少user_id'}, status=400)
        peer = get_object_or_404(User, id=peer_id)
        cs = _get_settings(request.user, peer)
        cs.cleared_before = timezone.now()
        cs.force_unread = False
        cs.save(update_fields=['cleared_before', 'force_unread', 'updated_at'])
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('清空对话错误', e)


# ------------------------------------------------------------------
# 标记已读/未读 / 置顶 / 免打扰 / 归档
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def mark_conversation_read_api(request):
    """将对话标记为已读"""
    try:
        from ..models import Message
        data = json.loads(request.body)
        peer_id = data.get('user_id')
        peer = get_object_or_404(User, id=peer_id)

        unread_qs = Message.objects.filter(
            sender=peer, recipient=request.user, is_read=False
        )
        unread_ids = list(unread_qs.values_list('id', flat=True))
        unread_qs.update(is_read=True, read_at=timezone.now())

        cs = _get_settings(request.user, peer)
        cs.last_read_at = timezone.now()
        cs.force_unread = False
        cs.save(update_fields=['last_read_at', 'force_unread', 'updated_at'])
        _push_message_read_event(peer.id, request.user.id, unread_ids, request.user.id)
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('标记已读错误', e)


@require_http_methods(["POST"])
@login_required
def mark_conversation_unread_api(request):
    """手动标记对话为未读"""
    try:
        data = json.loads(request.body)
        peer_id = data.get('user_id')
        peer = get_object_or_404(User, id=peer_id)
        cs = _get_settings(request.user, peer)
        cs.force_unread = True
        cs.save(update_fields=['force_unread', 'updated_at'])
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('标记未读错误', e)


def _toggle_field(request, field_name, timestamp_field=None):
    """通用 toggle 工具：body { user_id, value(bool) }"""
    try:
        data = json.loads(request.body)
        peer_id = data.get('user_id')
        value = bool(data.get('value'))
        if not peer_id:
            return JsonResponse({'error': '缺少user_id'}, status=400)
        peer = get_object_or_404(User, id=peer_id)
        cs = _get_settings(request.user, peer)
        setattr(cs, field_name, value)
        update_fields = [field_name, 'updated_at']
        if timestamp_field:
            setattr(cs, timestamp_field, timezone.now() if value else None)
            update_fields.append(timestamp_field)
        cs.save(update_fields=update_fields)
        return JsonResponse({'status': 'success', field_name: value})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)


@require_http_methods(["POST"])
@login_required
def toggle_pin_api(request):
    """置顶/取消置顶会话"""
    return _toggle_field(request, 'is_pinned', 'pinned_at')


@require_http_methods(["POST"])
@login_required
def toggle_mute_api(request):
    """免打扰/取消免打扰"""
    return _toggle_field(request, 'is_muted')


@require_http_methods(["POST"])
@login_required
def toggle_archive_api(request):
    """归档/取消归档"""
    return _toggle_field(request, 'is_archived', 'archived_at')


# ------------------------------------------------------------------
# 阅后即焚
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def set_disappearing_api(request):
    """设置阅后即焚"""
    try:
        data = json.loads(request.body)
        peer_id = data.get('user_id')
        enabled = bool(data.get('enabled'))
        ttl = int(data.get('ttl_seconds', 86400))
        if ttl < 0 or ttl > 604800 * 4:  # 最长 4 周
            return JsonResponse({'error': 'TTL 超出允许范围'}, status=400)
        peer = get_object_or_404(User, id=peer_id)
        cs = _get_settings(request.user, peer)
        cs.disappearing_enabled = enabled
        cs.disappearing_ttl_seconds = ttl
        cs.save(update_fields=['disappearing_enabled', 'disappearing_ttl_seconds', 'updated_at'])
        return JsonResponse({
            'status': 'success',
            'disappearing_enabled': enabled,
            'disappearing_ttl_seconds': ttl,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('阅后即焚设置错误', e)


@require_http_methods(["GET"])
@login_required
def get_conversation_settings_api(request):
    """获取当前用户对某 peer 的会话设置"""
    peer_id = request.GET.get('user_id')
    if not peer_id:
        return JsonResponse({'error': '缺少user_id'}, status=400)
    peer = get_object_or_404(User, id=peer_id)
    cs = _get_settings(request.user, peer)
    return JsonResponse({'status': 'success', 'settings': _conversation_settings_payload(cs)})


# ------------------------------------------------------------------
# 搜索 / 导出
# ------------------------------------------------------------------
@require_http_methods(["GET"])
@login_required
def search_messages_api(request):
    """跨会话全局搜索"""
    try:
        from ..models import Message
        q = request.GET.get('q', '').strip()
        if not q or len(q) < 2:
            return JsonResponse({'results': []})
        qs = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).exclude(is_recalled=True).filter(content__icontains=q).order_by('-created_at')[:40]

        results = []
        for m in qs:
            if m.sender_id == request.user.id and m.deleted_for_sender:
                continue
            if m.recipient_id == request.user.id and m.deleted_for_recipient:
                continue
            peer = m.recipient if m.sender_id == request.user.id else m.sender
            cs = _get_settings(request.user, peer)
            if cs.cleared_before and m.created_at <= cs.cleared_before:
                continue
            results.append({
                'id': m.id,
                'peer_id': peer.id,
                'peer_username': peer.username,
                'peer_avatar': _get_avatar_url(peer),
                'content': m.content,
                'created_at': m.created_at.isoformat(),
                'is_own': m.sender_id == request.user.id,
            })
        return JsonResponse({'status': 'success', 'results': results})
    except Exception as e:
        return _server_error_response('消息搜索错误', e)


@require_http_methods(["GET"])
@login_required
def export_conversation_api(request):
    """导出与某用户的聊天记录为 TXT"""
    try:
        peer_id = request.GET.get('user_id')
        if not peer_id:
            return JsonResponse({'error': '缺少user_id'}, status=400)
        peer = get_object_or_404(User, id=peer_id)
        cs = _get_settings(request.user, peer)
        messages_qs = _visible_messages_qs(request.user, peer, cs)

        lines = [
            f"聊天记录：{request.user.username} 与 {peer.username}",
            f"导出时间：{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"消息数量：{messages_qs.count()}",
            "-" * 60,
            "",
        ]
        for m in messages_qs:
            t = m.created_at.strftime('%Y-%m-%d %H:%M:%S')
            sender_name = m.sender.username
            lines.append(f"[{t}] {sender_name}:")
            for ln in (m.content or '').splitlines():
                lines.append(f"    {ln}")
            lines.append("")

        body = "\n".join(lines)
        response = HttpResponse(body, content_type='text/plain; charset=utf-8')
        fname = f"chat_with_{peer.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response
    except Exception as e:
        return _server_error_response('导出聊天记录错误', e)


# ------------------------------------------------------------------
# 举报
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def report_user_api(request):
    """举报用户或单条消息"""
    try:
        from ..models import Message, MessageReport
        data = json.loads(request.body)
        reported_user_id = data.get('user_id')
        reason = data.get('reason', 'other')
        detail = (data.get('detail') or '').strip()[:1000]
        message_id = data.get('message_id')

        if not reported_user_id:
            return JsonResponse({'error': '缺少user_id'}, status=400)
        if reason not in dict(MessageReport.REASON_CHOICES):
            return JsonResponse({'error': '无效的举报原因'}, status=400)

        reported_user = get_object_or_404(User, id=reported_user_id)
        if reported_user == request.user:
            return JsonResponse({'error': '不能举报自己'}, status=400)

        message = None
        if message_id:
            try:
                message = Message.objects.get(id=message_id)
            except Message.DoesNotExist:
                message = None

        if message is not None and request.user.id not in (message.sender_id, message.recipient_id):
            return JsonResponse({'error': '只有私信参与者才能举报该内容'}, status=403)

        MessageReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            message=message,
            reason=reason,
            detail=detail,
        )

        if message is not None:
            if not message.was_reported:
                message.was_reported = True
                message.pending_purge_at = None
                message.save(update_fields=['was_reported', 'pending_purge_at'])
            from ..models import AttachmentReport

            for attachment in message.attachments.all():
                if not attachment.was_reported:
                    attachment.was_reported = True
                    attachment.save(update_fields=['was_reported'])
                AttachmentReport.objects.get_or_create(
                    attachment=attachment,
                    reporter=request.user,
                    status='pending',
                    defaults={
                        'reason': reason,
                        'detail': detail,
                    }
                )

        return JsonResponse({'status': 'success', 'message': '举报已提交，我们会尽快处理'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('举报错误', e)


# ------------------------------------------------------------------
# 私信偏好设置（保留）
# ------------------------------------------------------------------
@require_http_methods(["GET"])
@login_required
def get_message_preference_api(request):
    """获取用户的私信偏好设置"""
    try:
        from ..models import MessagePreference

        target_user_id = request.GET.get('user_id')
        if target_user_id:
            target_user = get_object_or_404(User, id=target_user_id)
            pref, _ = MessagePreference.objects.get_or_create(user=target_user)
        else:
            pref, _ = MessagePreference.objects.get_or_create(user=request.user)

        return JsonResponse({
            'status': 'success',
            'preference': {
                'allow_messages': pref.allow_messages,
                'message_mode': pref.message_mode,
                'show_read_status': pref.show_read_status,
                'auto_reply_enabled': pref.auto_reply_enabled,
                'auto_reply_text': pref.auto_reply_text,
                'notify_new_message': pref.notify_new_message,
                'browser_new_message': pref.browser_new_message,
            }
        })
    except Exception as e:
        return _server_error_response('获取私信设置错误', e)


@require_http_methods(["POST"])
@login_required
def update_message_preference_api(request):
    """更新用户的私信偏好设置"""
    try:
        from ..models import MessagePreference
        data = json.loads(request.body)
        pref, _ = MessagePreference.objects.get_or_create(user=request.user)
        if 'allow_messages' in data:
            pref.allow_messages = data['allow_messages']
        if 'message_mode' in data and data['message_mode'] in ['all', 'followers_only', 'following_only', 'disabled']:
            pref.message_mode = data['message_mode']
        if 'show_read_status' in data:
            pref.show_read_status = data['show_read_status']
        if 'auto_reply_enabled' in data:
            pref.auto_reply_enabled = data['auto_reply_enabled']
        if 'auto_reply_text' in data:
            pref.auto_reply_text = data['auto_reply_text'][:500]
        if 'notify_new_message' in data:
            pref.notify_new_message = bool(data['notify_new_message'])
        if 'browser_new_message' in data:
            pref.browser_new_message = bool(data['browser_new_message'])
        pref.save()
        return JsonResponse({'status': 'success', 'message': '设置已更新'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('更新私信设置错误', e)


# ------------------------------------------------------------------
# 屏蔽
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def block_user_api(request):
    """屏蔽用户"""
    try:
        from ..models import UserBlocklist
        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')
        reason = data.get('reason', '')
        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)
        blocked_user = get_object_or_404(User, id=blocked_user_id)
        if blocked_user == request.user:
            return JsonResponse({'error': '无法屏蔽自己'}, status=400)
        blocklist, created = UserBlocklist.objects.get_or_create(
            user=request.user, blocked_user=blocked_user, defaults={'reason': reason}
        )
        if not created:
            blocklist.reason = reason
            blocklist.save()
        return JsonResponse({'status': 'success', 'message': '已屏蔽用户'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('屏蔽用户错误', e)


@require_http_methods(["POST"])
@login_required
def unblock_user_api(request):
    """取消屏蔽"""
    try:
        from ..models import UserBlocklist
        data = json.loads(request.body)
        blocked_user_id = data.get('user_id')
        if not blocked_user_id:
            return JsonResponse({'error': '缺少user_id参数'}, status=400)
        UserBlocklist.objects.filter(
            user=request.user, blocked_user_id=blocked_user_id
        ).delete()
        return JsonResponse({'status': 'success', 'message': '已取消屏蔽'})
    except Exception as e:
        return _server_error_response('取消屏蔽错误', e)


@require_http_methods(["GET"])
@login_required
def get_blocked_users_api(request):
    """获取屏蔽列表"""
    try:
        from ..models import UserBlocklist
        blocked = UserBlocklist.objects.filter(user=request.user).select_related('blocked_user')
        blocked_list = []
        for item in blocked:
            blocked_list.append({
                'id': item.blocked_user.id,
                'username': item.blocked_user.username,
                'avatar_url': _get_avatar_url(item.blocked_user),
                'avatar': _get_avatar_url(item.blocked_user),
                'blocked_at': item.created_at.strftime('%Y-%m-%d') if hasattr(item, 'created_at') and item.created_at else None,
                'reason': item.reason,
            })
        return JsonResponse({'status': 'success', 'blocked_users': blocked_list})
    except Exception as e:
        return _server_error_response('获取屏蔽列表错误', e)


# ------------------------------------------------------------------
# 用户资料与搜索
# ------------------------------------------------------------------
@require_http_methods(["GET"])
def get_user_public_profile_api(request, user_id):
    try:
        user = get_object_or_404(User, id=user_id)
        profile = user.profile
        notes_count = Note.objects.filter(author=user, is_public=True).count()
        views_count = Note.objects.filter(author=user, is_public=True).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0
        likes_count = ProfileLike.objects.filter(profile=profile).count()
        return JsonResponse({
            'status': 'success',
            'id': user.id,
            'username': user.username,
            'avatar': _get_avatar_url(user),
            'bio': profile.bio or '',
            'notes_count': notes_count,
            'views_count': views_count,
            'likes_count': likes_count,
        })
    except Exception as e:
        return _server_error_response('获取用户信息错误', e)


@require_http_methods(["GET"])
def search_users_api(request):
    """精准搜索（防用户枚举）

    三路 iexact 精准匹配：username / email / search_code
    不做模糊搜索、不返回前缀建议、空结果统一返回 {'users': []}
    被搜索方的 discoverable_by_username / discoverable_by_email 开关控制是否可被检索到；
    search_code 属于主动分享的公开短码，无需额外开关即可命中。
    """
    try:
        from ..models import Profile

        query = (request.GET.get('q') or '').strip()
        if len(query) < 3 or len(query) > 254:
            return JsonResponse({'users': []})

        viewer_id = request.user.id if request.user.is_authenticated else None
        found = None
        via = None

        # 1. search_code（8 位大写字母数字，优先匹配且无需开关）
        candidate_code = query.upper()
        if 6 <= len(candidate_code) <= 12 and candidate_code.isalnum():
            try:
                profile = Profile.objects.select_related('user').get(search_code=candidate_code)
                found = profile.user
                via = 'code'
            except Profile.DoesNotExist:
                pass

        # 2. username iexact（尊重 discoverable_by_username）
        if not found:
            try:
                candidate = User.objects.select_related('profile').get(username__iexact=query)
                if getattr(candidate.profile, 'discoverable_by_username', False):
                    found = candidate
                    via = 'username'
            except User.DoesNotExist:
                pass

        # 3. email iexact（尊重 discoverable_by_email，且必须形如邮箱）
        if not found and '@' in query:
            try:
                candidate = User.objects.select_related('profile').get(email__iexact=query)
                if getattr(candidate.profile, 'discoverable_by_email', False):
                    found = candidate
                    via = 'email'
            except User.DoesNotExist:
                pass

        # 不能搜到自己、不能搜到被搜到者已屏蔽 viewer 的情况
        if found and viewer_id and found.id == viewer_id:
            found = None
        if found and viewer_id:
            from ..models import UserBlocklist
            if UserBlocklist.objects.filter(
                (Q(user=found, blocked_user_id=viewer_id)) |
                (Q(user_id=viewer_id, blocked_user=found))
            ).exists():
                found = None  # 对方屏蔽了搜索者，仍走中性文案

        if not found:
            return JsonResponse({'users': []})

        return JsonResponse({
            'users': [{
                'id': found.id,
                'username': found.username,
                'avatar': _get_avatar_url(found),
                'bio': getattr(getattr(found, 'profile', None), 'bio', '') or '',
                'matched_by': via,
            }],
        })
    except Exception as e:
        return _server_error_response('搜索用户错误', e)


@login_required
def messages_view(request):
    """私信页面"""
    return render(request, 'messages/messages.html', {
        'realtime_enabled': getattr(settings, 'REALTIME_MESSAGES_ENABLED', False),
        'realtime_ws_path': getattr(settings, 'REALTIME_MESSAGES_PATH', '/ws/messages/'),
    })


# ------------------------------------------------------------------
# 未读统计 / 账户可发现性
# ------------------------------------------------------------------
@require_http_methods(["GET"])
@login_required
def get_unread_messages_count_api(request):
    """当前用户的未读私信总数（供导航栏角标轮询）"""
    try:
        from ..models import Message
        total = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            is_recalled=False,
            deleted_for_recipient=False,
        ).count()
        return JsonResponse({'status': 'success', 'unread_count': total})
    except Exception as e:
        return _server_error_response('获取未读数错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def update_discoverability_api(request):
    """账户可发现性开关 + search_code 管理

    GET : 读取当前开关与 search_code
    POST: body {discoverable_by_username?, discoverable_by_email?, regenerate_code?}
    """
    import secrets
    import string
    from ..models import Profile

    profile = request.user.profile

    if request.method == 'GET':
        return JsonResponse({
            'status': 'success',
            'discoverable_by_username': profile.discoverable_by_username,
            'discoverable_by_email': profile.discoverable_by_email,
            'search_code': profile.search_code or '',
        })

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)

    update_fields = []
    if 'discoverable_by_username' in data:
        profile.discoverable_by_username = bool(data['discoverable_by_username'])
        update_fields.append('discoverable_by_username')
    if 'discoverable_by_email' in data:
        profile.discoverable_by_email = bool(data['discoverable_by_email'])
        update_fields.append('discoverable_by_email')

    if data.get('regenerate_code'):
        abc = string.ascii_uppercase + string.digits
        for _ in range(8):
            code = ''.join(secrets.choice(abc) for _ in range(8))
            if not Profile.objects.filter(search_code=code).exclude(pk=profile.pk).exists():
                profile.search_code = code
                update_fields.append('search_code')
                break
        else:
            return JsonResponse({'error': '生成搜索短码失败，请稍后重试'}, status=500)

    if update_fields:
        profile.save(update_fields=update_fields)

    return JsonResponse({
        'status': 'success',
        'discoverable_by_username': profile.discoverable_by_username,
        'discoverable_by_email': profile.discoverable_by_email,
        'search_code': profile.search_code or '',
    })
