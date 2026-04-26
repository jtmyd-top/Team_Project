# knowledge_project/views/message.py
"""私信 / 对话设置 / 屏蔽 / 用户搜索与公开资料相关视图"""
import json
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Note, ProfileLike

logger = logging.getLogger(__name__)

# 撤回时间窗口（秒）
RECALL_WINDOW_SECONDS = 120

# 每天主动发起新对话（陌生人）的免验证配额，超过后必须通过 Turnstile
NEW_CONV_DAILY_LIMIT = 5
# 同一对话的新私信邮件节流窗口（秒）
EMAIL_NOTIFY_WINDOW_SECONDS = 15 * 60


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


def _apply_disappearing(viewer, peer, viewer_settings=None):
    """懒惰清理：任一方开启阅后即焚且消息已读超过 TTL 即销毁。

    - 读取 viewer / peer 双方的 ConversationSettings
    - 任一方 disappearing_enabled=True 即生效，TTL 取所有开启方中的最短值
    - TTL=0 表示「阅读后立即」—— 所有已读消息全部立即销毁
    - 销毁方式：is_recalled=True（双方视图都不可见）
    """
    from ..models import ConversationSettings, Message

    if viewer_settings is None:
        viewer_settings = ConversationSettings.objects.filter(user=viewer, peer=peer).first()
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
    }


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
        if pref.last_email_notified_at and \
                (now - pref.last_email_notified_at).total_seconds() < EMAIL_NOTIFY_WINDOW_SECONDS:
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
            f"如不希望再收到此类通知，可在「设置 → 隐私与通信」中关闭邮件提醒。"
        )
        SmartEmailSender().send_email(subject, body, [recipient.email])
        pref.last_email_notified_at = now
        pref.save(update_fields=['last_email_notified_at', 'updated_at'])
    except Exception as e:
        logger.warning(f"新私信邮件通知失败: {e}")


# ------------------------------------------------------------------
# 发送 / 获取 / 对话列表
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def send_message_api(request):
    """发送私信"""
    try:
        from ..models import Message, MessagePreference, UserBlocklist, NewConversationQuotaLog, UserFollow

        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        try:
            content = _body_string(data, 'content')
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        if not recipient_id or not content:
            return JsonResponse({'error': '缺少必需参数'}, status=400)
        if len(content) > 5000:
            return JsonResponse({'error': '消息内容不能超过5000字'}, status=400)

        recipient = get_object_or_404(User, id=recipient_id)
        if recipient == request.user:
            return JsonResponse({'error': '不能给自己发送私信'}, status=400)

        # 检查是否被对方屏蔽
        is_blocked = UserBlocklist.objects.filter(
            user=recipient, blocked_user=request.user
        ).exists()
        if is_blocked:
            return JsonResponse({'error': '无法向此用户发送私信'}, status=403)

        # 检查接收者是否开启了私信
        pref, _ = MessagePreference.objects.get_or_create(user=recipient)
        blocked_by_sender = UserBlocklist.objects.filter(
            user=request.user, blocked_user=recipient
        ).exists()
        if blocked_by_sender:
            return JsonResponse({'error': '你已屏蔽此用户，解除屏蔽后才能发送私信'}, status=403)
        if not pref.allow_messages or pref.message_mode == 'disabled':
            return JsonResponse({'error': '此用户未开启私信功能'}, status=403)

        # message_mode:
        # - followers_only: 仅允许“关注了接收者”的用户私信（发送者 -> 接收者）
        # - following_only: 仅允许“被接收者关注”的用户私信（接收者 -> 发送者）
        if pref.message_mode == 'followers_only':
            is_follower = UserFollow.objects.filter(
                follower=request.user,
                following=recipient
            ).exists()
            if not is_follower:
                return JsonResponse({'error': '对方仅接收其关注者的私信'}, status=403)
        elif pref.message_mode == 'following_only':
            is_followed_by_recipient = UserFollow.objects.filter(
                follower=recipient,
                following=request.user
            ).exists()
            if not is_followed_by_recipient:
                return JsonResponse({'error': '对方仅接收其已关注用户的私信'}, status=403)

        # 新对话限流：超出免验证配额时必须通过 Turnstile
        is_new_conv = _is_new_conversation(request.user, recipient)
        turnstile_passed = False
        if is_new_conv:
            quota_used = _today_new_conv_count(request.user)
            if quota_used >= NEW_CONV_DAILY_LIMIT:
                raw_turnstile_token = data.get('turnstile_token')
                if raw_turnstile_token in (None, ''):
                    return JsonResponse({
                        'error': '今日新对话数量已达上限，请完成人机验证',
                        'need_turnstile': True,
                        'quota_used': quota_used,
                        'quota_limit': NEW_CONV_DAILY_LIMIT,
                    }, status=429)
                if not isinstance(raw_turnstile_token, str):
                    return JsonResponse({
                        'error': '人机验证参数无效，请重试',
                        'need_turnstile': True,
                    }, status=400)
                turnstile_token = raw_turnstile_token.strip()
                if not turnstile_token:
                    return JsonResponse({
                        'error': '今日新对话数量已达上限，请完成人机验证',
                        'need_turnstile': True,
                        'quota_used': quota_used,
                        'quota_limit': NEW_CONV_DAILY_LIMIT,
                    }, status=429)
                from ..utils.turnstile import verify_turnstile_token
                from ..utils.request_utils import get_client_ip
                if not verify_turnstile_token(turnstile_token, get_client_ip(request)):
                    return JsonResponse({
                        'error': '人机验证失败，请重试',
                        'need_turnstile': True,
                    }, status=403)
                turnstile_passed = True

        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=content,
        )

        # 记录新对话配额日志（总是记录，便于审计；限流字段标记是否走了 Turnstile）
        if is_new_conv:
            NewConversationQuotaLog.objects.create(
                user=request.user,
                peer=recipient,
                turnstile_passed=turnstile_passed,
            )

        # 发送者端自动清除对方的 force_unread；新消息自动把对方从归档中拉回
        recipient_settings = _get_settings(recipient, request.user)
        recipient_settings.force_unread = False
        if recipient_settings.is_archived:
            recipient_settings.is_archived = False
            recipient_settings.archived_at = None
        recipient_settings.save()

        # 发送者端：更新自己的 last_read_at，防止自己看到「未读」
        sender_settings = _get_settings(request.user, recipient)
        sender_settings.last_read_at = timezone.now()
        sender_settings.force_unread = False
        sender_settings.save()

        # 异步兜底：邮件通知（尊重 notify_new_message + 15 分钟聚合）
        _maybe_send_new_message_email(request.user, recipient, content)

        # 发送动作也触发一次阅后即焚清理（若发送者或对方有超 TTL 的旧已读消息）
        _apply_disappearing(request.user, recipient, sender_settings)

        return JsonResponse({
            'status': 'success',
            'message': _message_payload(message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"发送私信错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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

        # 标记接收到的消息为已读（仅对 recipient=viewer 的未读消息）
        from ..models import Message
        Message.objects.filter(
            recipient=request.user, sender=other_user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        # 更新 viewer 的 last_read_at 并清除 force_unread
        viewer_settings.last_read_at = timezone.now()
        viewer_settings.force_unread = False
        viewer_settings.save()

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
        logger.error(f"获取私信列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        ).exclude(is_recalled=True).order_by('-created_at')

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

        blocked_ids = set(
            UserBlocklist.objects.filter(user=request.user).values_list('blocked_user_id', flat=True)
        )

        conversations = []
        for peer_id, last_msg in ordered_peers:
            try:
                peer = User.objects.get(id=peer_id)
            except User.DoesNotExist:
                continue
            cs = _get_settings(request.user, peer)

            # 懒惰清理：任一方开启阅后即焚时，遍历到此对话就触发一次
            _apply_disappearing(request.user, peer, cs)

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

            unread = _count_unread(request.user, peer, cs)
            if scope == 'unread' and unread == 0:
                continue

            preview = last_msg.content or ''
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
        logger.error(f"获取对话列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
            age = (timezone.now() - msg.created_at).total_seconds()
            if age > RECALL_WINDOW_SECONDS:
                return JsonResponse({
                    'error': f'发送超过 {RECALL_WINDOW_SECONDS // 60} 分钟的消息不能撤回'
                }, status=403)
            msg.is_recalled = True
            msg.recalled_at = timezone.now()
            msg.save(update_fields=['is_recalled', 'recalled_at'])
            return JsonResponse({'status': 'success', 'scope': 'both'})

        # scope == self
        if request.user.id == msg.sender_id:
            msg.deleted_for_sender = True
        if request.user.id == msg.recipient_id:
            msg.deleted_for_recipient = True
        msg.save(update_fields=['deleted_for_sender', 'deleted_for_recipient'])
        return JsonResponse({'status': 'success', 'scope': 'self'})
    except Exception as e:
        logger.error(f"删除消息错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"清空对话错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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

        Message.objects.filter(
            sender=peer, recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        cs = _get_settings(request.user, peer)
        cs.last_read_at = timezone.now()
        cs.force_unread = False
        cs.save(update_fields=['last_read_at', 'force_unread', 'updated_at'])
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"标记已读错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"标记未读错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"阅后即焚设置错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"消息搜索错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"导出聊天记录错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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

        MessageReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            message=message,
            reason=reason,
            detail=detail,
        )
        return JsonResponse({'status': 'success', 'message': '举报已提交，我们会尽快处理'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"举报错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
            }
        })
    except Exception as e:
        logger.error(f"获取私信设置错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
            pref.notify_new_message = data['notify_new_message']
        pref.save()
        return JsonResponse({'status': 'success', 'message': '设置已更新'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        logger.error(f"更新私信设置错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"屏蔽用户错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"取消屏蔽错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"获取屏蔽列表错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
        logger.error(f"获取用户信息错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
            if UserBlocklist.objects.filter(user=found, blocked_user_id=viewer_id).exists():
                found = None  # 对方屏蔽了搜索者，仍走中性文案

        if found and viewer_id:
            from ..models import UserBlocklist
            if UserBlocklist.objects.filter(user_id=viewer_id, blocked_user=found).exists():
                found = None
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
        logger.error(f"搜索用户错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def messages_view(request):
    """私信页面"""
    return render(request, 'messages/messages.html')


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
        logger.error(f"获取未读数错误: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
