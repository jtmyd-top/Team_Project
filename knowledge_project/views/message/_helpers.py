# knowledge_project/views/message/_helpers.py
"""私信子包通用工具函数。

仅依赖顶层 models / realtime / Django 公共组件,不导入任何 view 子模块,
避免循环引用。view 子文件通过 `from ._helpers import xxx` 取用。
"""
import base64
import binascii
import json
import logging
import os
import threading
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404  # noqa: F401  (保留 import 以便后续工具复用)
from django.utils import timezone

from ...realtime import push_user_event
from ...utils.session_activity import (
    has_recent_messages_page_activity,
    has_recent_user_activity,
)
from ._constants import (
    EMAIL_NOTIFY_WINDOW_SECONDS,
    MERGED_FORWARD_MAX_DEPTH,
    MERGED_FORWARD_MAX_ENCODED_LENGTH,
    MERGED_FORWARD_MAX_FIELD_LENGTH,
    MERGED_FORWARD_MAX_ITEMS,
    MERGED_FORWARD_MAX_SEARCHABLE_TEXT,
    MERGED_FORWARD_PREFIX,
    MESSAGE_ATTACHMENT_MAX_COUNT,
    MESSAGE_CONTENT_MAX_LENGTH,
    MESSAGE_PURGE_DELAY_DAYS,
    MESSAGES_PAGE_SKIP_EMAIL_WINDOW_SECONDS,
    NEW_CONV_DAILY_LIMIT,  # noqa: F401  (子模块从 _helpers 走时复用,避免到处分散)
    ONLINE_SKIP_EMAIL_WINDOW_SECONDS,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 基础渲染 / 错误
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
    from ...models import ConversationSettings
    settings_obj, _ = ConversationSettings.objects.get_or_create(user=user, peer=peer)
    return settings_obj


def _server_error_response(log_message, exc, public_message='服务器错误'):
    logger.error("%s: %s", log_message, exc, exc_info=True)
    return JsonResponse({'error': public_message}, status=500)


# ------------------------------------------------------------------
# 合并转发解析
# ------------------------------------------------------------------
def _trim_text(value, max_length=MERGED_FORWARD_MAX_FIELD_LENGTH):
    text = str(value or '')
    return text[:max_length]


def _normalize_merged_forward_attachment(attachment):
    if not isinstance(attachment, dict):
        return None
    return {
        'id': attachment.get('id'),
        'type': _trim_text(attachment.get('type'), 32),
        'name': _trim_text(attachment.get('name'), 255),
        'mime_type': _trim_text(attachment.get('mime_type'), 120),
        'size': attachment.get('size') or 0,
        'url': _trim_text(attachment.get('url'), 1000),
    }


def _normalize_merged_forward_item(item):
    if not isinstance(item, dict):
        return None
    attachments = item.get('attachments')
    if not isinstance(attachments, list):
        attachments = []
    return {
        'id': item.get('id'),
        'sender': _trim_text(item.get('sender') or '未知用户', 120),
        'avatar': _trim_text(item.get('avatar') or '/static/img/default-avatar.png', 1000),
        'is_own': item.get('is_own') is True,
        'content': _trim_text(item.get('content')),
        'preview': _trim_text(item.get('preview') or item.get('content')),
        'time': _trim_text(item.get('time'), 80),
        'attachments': [
            normalized for normalized in (
                _normalize_merged_forward_attachment(attachment)
                for attachment in attachments[:MESSAGE_ATTACHMENT_MAX_COUNT]
            )
            if normalized
        ],
    }


def _parse_merged_forward(content, validate_limits=False):
    raw = (content or '').strip()
    if not raw.startswith(MERGED_FORWARD_PREFIX):
        return None
    if validate_limits and len(raw) > MERGED_FORWARD_MAX_ENCODED_LENGTH:
        raise ValueError(f'合并转发内容过长，请减少消息数量后再试')
    try:
        encoded = raw[len(MERGED_FORWARD_PREFIX):].encode('ascii')
        decoded = base64.b64decode(encoded, validate=True).decode('utf-8')
        data = json.loads(decoded)
    except (UnicodeDecodeError, binascii.Error, ValueError, TypeError, json.JSONDecodeError):
        if validate_limits:
            raise ValueError('合并转发内容格式无效')
        return None
    if not isinstance(data, dict) or data.get('type') != 'merged_forward':
        if validate_limits:
            raise ValueError('合并转发内容格式无效')
        return None
    items = data.get('items')
    if not isinstance(items, list):
        if validate_limits:
            raise ValueError('合并转发内容格式无效')
        return None
    if validate_limits and len(items) > MERGED_FORWARD_MAX_ITEMS:
        raise ValueError(f'每次最多只能合并转发 {MERGED_FORWARD_MAX_ITEMS} 条消息')

    normalized_items = [_normalize_merged_forward_item(item) for item in items]
    normalized_items = [item for item in normalized_items if item]
    if validate_limits and not normalized_items:
        raise ValueError('合并转发内容不能为空')

    try:
        count = int(data.get('count') or len(normalized_items) or 0)
    except (TypeError, ValueError):
        count = len(normalized_items)

    return {
        'type': 'merged_forward',
        'title': _trim_text(data.get('title') or '聊天记录', 200),
        'source': _trim_text(data.get('source'), 200),
        'count': count,
        'items': normalized_items,
    }


def _merged_forward_preview(content):
    data = _parse_merged_forward(content)
    if not data:
        return ''
    lines = []
    for item in data.get('items', [])[:3]:
        if not isinstance(item, dict):
            continue
        sender = str(item.get('sender') or '未知用户')
        preview = str(item.get('preview') or item.get('content') or '[附件]')
        lines.append(f'{sender}: {preview}')
    return '[聊天记录] ' + (' / '.join(lines) or str(data.get('title') or '聊天记录'))


def _merged_forward_searchable_text(data, depth=0):
    if not data or depth > MERGED_FORWARD_MAX_DEPTH:
        return ''
    parts = [
        str(data.get('title') or ''),
        str(data.get('source') or ''),
    ]
    for item in data.get('items', [])[:MERGED_FORWARD_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        parts.append(str(item.get('sender') or ''))
        content = str(item.get('content') or '')
        nested = _parse_merged_forward(content) if depth < MERGED_FORWARD_MAX_DEPTH else None
        if nested:
            parts.append(_merged_forward_searchable_text(nested, depth + 1))
        else:
            parts.append(content)
        parts.append(str(item.get('preview') or ''))
        attachments = item.get('attachments') if isinstance(item.get('attachments'), list) else []
        for attachment in attachments[:MESSAGE_ATTACHMENT_MAX_COUNT]:
            if isinstance(attachment, dict):
                parts.append(str(attachment.get('name') or ''))
    return '\n'.join(part for part in parts if part).strip()[:MERGED_FORWARD_MAX_SEARCHABLE_TEXT]


def _message_searchable_text(content, attachments=None):
    merged = _parse_merged_forward(content)
    if merged:
        searchable = _merged_forward_searchable_text(merged)
    else:
        searchable = str(content or '')
    for attachment in attachments or []:
        searchable += f"\n{getattr(attachment, 'original_name', '') or ''}"
    return searchable.strip()[:MERGED_FORWARD_MAX_SEARCHABLE_TEXT]


def _validate_message_content(content):
    if not content:
        return
    if content.startswith(MERGED_FORWARD_PREFIX):
        _parse_merged_forward(content, validate_limits=True)
        return
    if len(content) > MESSAGE_CONTENT_MAX_LENGTH:
        raise ValueError(f'消息内容不能超过{MESSAGE_CONTENT_MAX_LENGTH}字')


# ------------------------------------------------------------------
# 搜索辅助
# ------------------------------------------------------------------
def _message_search_q(query):
    return Q(content__icontains=query) | Q(searchable_text__icontains=query)


def _message_search_snippet(message, query, max_length=220):
    text = (message.searchable_text or '').strip()
    if query and query.lower() not in text.lower():
        text = ''
    if not text:
        text = _message_preview(message)
    text = ' '.join(str(text or '').split())
    if len(text) <= max_length:
        return text

    lowered = text.lower()
    index = lowered.find(query.lower()) if query else -1
    if index < 0:
        return text[:max_length - 1] + '…'
    start = max(0, index - max_length // 3)
    end = min(len(text), start + max_length)
    start = max(0, end - max_length)
    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(text) else ''
    return prefix + text[start:end] + suffix


# ------------------------------------------------------------------
# 物理清理 / 撤回 / 举报状态
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# 实时事件推送
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# 可见消息查询 / 阅后即焚 / 未读计算
# ------------------------------------------------------------------
def _visible_messages_qs(viewer, peer, viewer_settings=None):
    """返回在 viewer 视角下可见的 viewer<->peer 消息 queryset（按时间升序）"""
    from ...models import Message
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
    from ...models import ConversationSettings, Message

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
    from ...models import Message
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


# ------------------------------------------------------------------
# 序列化 payload
# ------------------------------------------------------------------
def _message_payload(msg, viewer=None):
    merged_forward = _parse_merged_forward(msg.content)
    return {
        'id': msg.id,
        'sender': msg.sender.username,
        'sender_id': msg.sender_id,
        'sender_avatar': _get_avatar_url(msg.sender),
        'recipient': msg.recipient.username,
        'recipient_id': msg.recipient_id,
        'content': msg.content,
        'content_preview': _merged_forward_preview(msg.content) if merged_forward else '',
        'merged_forward': merged_forward,
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


def _clone_forwarded_attachments(source_message, sender, target_message):
    from ...models import MessageAttachment

    created = []
    for source in source_message.attachments.all():
        forwarded = MessageAttachment.objects.create(
            uploader=sender,
            message=target_message,
            file=source.file.name,
            original_name=source.original_name,
            attachment_type=source.attachment_type,
            mime_type=source.mime_type,
            size=source.size,
            was_reported=source.was_reported,
        )
        created.append(forwarded)
    return created


def _message_preview(msg):
    merged_preview = _merged_forward_preview(msg.content)
    if merged_preview:
        return merged_preview
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


# ------------------------------------------------------------------
# 附件 IO
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# 新对话配额
# ------------------------------------------------------------------
def _is_new_conversation(sender, recipient):
    """判断 sender -> recipient 是否属于"新对话"

    没有历史往来消息（任意方向、不计撤回/自删）即视为新对话。
    """
    from ...models import Message
    return not Message.objects.filter(
        (Q(sender=sender) & Q(recipient=recipient)) |
        (Q(sender=recipient) & Q(recipient=sender))
    ).exists()


def _today_new_conv_count(user):
    """当日（本地日）该用户主动发起的新对话次数"""
    from ...models import NewConversationQuotaLog
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return NewConversationQuotaLog.objects.filter(
        user=user, created_at__gte=start
    ).count()


# ------------------------------------------------------------------
# 发送 / 转发 输入校验与权限
# ------------------------------------------------------------------
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
    _validate_message_content(content)
    return recipient_id, content, attachment_ids


def _load_message_attachments(user, attachment_ids):
    if not attachment_ids:
        return []
    from ...models import MessageAttachment

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


def _format_sanction_expiry(sanction):
    """把制裁到期时间格式化为面向用户的中文提示。"""
    if sanction is None or sanction.expires_at is None:
        return '永久'
    return timezone.localtime(sanction.expires_at).strftime('%Y-%m-%d %H:%M')


def _check_send_permissions(sender, recipient):
    from ...models import MessagePreference, UserBlocklist, UserFollow, UserSanction

    # 发送方被禁言私信：直接拦截
    mute = UserSanction.is_muted(sender)
    if mute is not None:
        return JsonResponse(
            {'error': f'你已被禁止发送私信，解除时间：{_format_sanction_expiry(mute)}'},
            status=403,
        ), None

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

    from ...utils.turnstile import verify_turnstile_token
    from ...utils.request_utils import get_client_ip
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
    """低频私信邮件通知：只在用户明显离站时发送。"""
    try:
        from ...models import MessagePreference
        pref, _ = MessagePreference.objects.get_or_create(user=recipient)
        if not pref.notify_new_message:
            return
        if not recipient.email:
            return
        if _has_recent_active_session(recipient):
            logger.info("跳过私信邮件通知：recipient=%s 最近仍在线", recipient.id)
            return
        if _has_recent_messages_page_session(recipient):
            logger.info("跳过私信邮件通知：recipient=%s 正在使用私信页面", recipient.id)
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

        from ...utils.smart_email_sender import SmartEmailSender
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
# 在线状态(用于邮件抑制)
# ------------------------------------------------------------------
def _has_recent_active_session(user):
    return has_recent_user_activity(user.id, ONLINE_SKIP_EMAIL_WINDOW_SECONDS)


def _has_recent_messages_page_session(user):
    return has_recent_messages_page_activity(user.id, MESSAGES_PAGE_SKIP_EMAIL_WINDOW_SECONDS)


# ------------------------------------------------------------------
# 通用 toggle (用于会话设置)
# ------------------------------------------------------------------
def _toggle_field(request, field_name, timestamp_field=None):
    """通用 toggle 工具：body { user_id, value(bool) }"""
    from django.contrib.auth.models import User

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
