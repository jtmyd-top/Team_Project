# knowledge_project/views/message/conversation.py
"""对话内的所有操作:发送 / 转发 / 读取 / 列表 / 删除 / 撤回 /
标记 / 清空 / 置顶 / 免打扰 / 归档 / 阅后即焚 / 设置查询"""
import json
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ._constants import NEW_CONV_DAILY_LIMIT, RECALL_WINDOW_SECONDS
from ._helpers import (
    _apply_disappearing,
    _attachment_preview,
    _body_string,
    _check_send_permissions,
    _clone_forwarded_attachments,
    _conversation_settings_payload,
    _get_avatar_url,
    _get_settings,
    _is_new_conversation,
    _load_message_attachments,
    _maybe_send_new_message_email,
    _message_payload,
    _message_preview,
    _message_search_q,
    _message_searchable_text,
    _push_message_read_event,
    _push_message_recalled_event,
    _push_new_message_events,
    _refresh_message_purge_schedule,
    _refresh_purge_schedule_for_messages,
    _server_error_response,
    _today_new_conv_count,
    _toggle_field,
    _update_conversation_state,
    _validate_message_content,
    _validate_send_message_input,
    _verify_new_conversation_quota,
    _visible_messages_qs,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 发送 / 转发
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def send_message_api(request):
    """发送私信"""
    try:
        from ...models import Message, MessageAttachment, NewConversationQuotaLog

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
                searchable_text=_message_searchable_text(content, attachments),
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
def forward_message_api(request):
    """转发单条消息；若原消息包含附件，则为新消息创建新的附件记录并复用同一物理文件路径。"""
    try:
        from ...models import Message, NewConversationQuotaLog

        data = json.loads(request.body)
        source_message_id = data.get('message_id')
        recipient_id = data.get('recipient_id')
        if not source_message_id or not recipient_id:
            return JsonResponse({'error': '缺少 message_id 或 recipient_id'}, status=400)

        source_message = get_object_or_404(
            Message.objects.select_related('sender', 'recipient').prefetch_related('attachments'),
            id=source_message_id,
        )
        if request.user.id not in (source_message.sender_id, source_message.recipient_id):
            return JsonResponse({'error': '无权转发该消息'}, status=403)

        recipient = get_object_or_404(User, id=recipient_id)
        permission_response, _ = _check_send_permissions(request.user, recipient)
        if permission_response is not None:
            return permission_response

        is_new_conv = _is_new_conversation(request.user, recipient)
        try:
            turnstile_passed = _verify_new_conversation_quota(request, data, recipient)
        except PermissionError as exc:
            if str(exc) == 'turnstile_failed':
                return JsonResponse({'error': '人机验证失败，请重试', 'need_turnstile': True}, status=403)
            quota_used = _today_new_conv_count(request.user)
            return JsonResponse({
                'error': '今日新对话数量已达上限，请完成人机验证',
                'need_turnstile': True,
                'quota_used': quota_used,
                'quota_limit': NEW_CONV_DAILY_LIMIT,
            }, status=429)

        content = _body_string(data, 'content', '').strip()
        if not content:
            content = source_message.content or _attachment_preview(source_message.attachments.first())
        if not content and not source_message.attachments.exists():
            return JsonResponse({'error': '原消息为空，无法转发'}, status=400)
        _validate_message_content(content)

        with transaction.atomic():
            forwarded_message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
            )
            forwarded_attachments = _clone_forwarded_attachments(source_message, request.user, forwarded_message)
            forwarded_message.searchable_text = _message_searchable_text(content, forwarded_attachments)
            forwarded_message.save(update_fields=['searchable_text'])

            if is_new_conv:
                NewConversationQuotaLog.objects.create(
                    user=request.user,
                    peer=recipient,
                    turnstile_passed=turnstile_passed,
                )

            sender_settings = _update_conversation_state(request.user, recipient)
            preview_for_email = content or _attachment_preview(forwarded_message.attachments.first())
            transaction.on_commit(
                lambda: _maybe_send_new_message_email(request.user, recipient, preview_for_email)
            )
            transaction.on_commit(lambda: _push_new_message_events(forwarded_message))

        _apply_disappearing(request.user, recipient, sender_settings)
        return JsonResponse({
            'status': 'success',
            'message': _message_payload(forwarded_message, viewer=request.user),
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except IntegrityError as e:
        logger.warning("转发私信数据库冲突: %s", e, exc_info=True)
        return JsonResponse({'error': '请求冲突，请稍后重试'}, status=409)
    except Exception as e:
        return _server_error_response('转发私信错误', e)


# ------------------------------------------------------------------
# 读取 / 列表
# ------------------------------------------------------------------
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
            messages_qs = messages_qs.filter(_message_search_q(query))

        # 强制求值为列表，后续的 is_read / is_recalled 更新不影响这份快照
        messages_list = list(messages_qs)
        unread_ids = [m.id for m in messages_list if m.sender_id == other_user.id and not m.is_read]

        # 标记接收到的消息为已读（仅对 recipient=viewer 的未读消息）
        from ...models import Message
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


@require_http_methods(["GET"])
@login_required
def get_message_conversations_api(request):
    """对话列表，支持 scope=all|unread|archived|blocked"""
    try:
        from ...models import Message, ConversationSettings, UserBlocklist

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
        from ...models import Message
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
        from ...models import Message
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
# 标记已读 / 未读
# ------------------------------------------------------------------
@require_http_methods(["POST"])
@login_required
def mark_conversation_read_api(request):
    """将对话标记为已读"""
    try:
        from ...models import Message
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


# ------------------------------------------------------------------
# 置顶 / 免打扰 / 归档 / 阅后即焚 / 设置查询
# ------------------------------------------------------------------
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
