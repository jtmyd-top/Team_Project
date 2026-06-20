"""Conversation delete views."""
from .common import *  # noqa: F401, F403


@require_http_methods(["POST", "DELETE"])
@login_required
def delete_message_api(request, message_id):
    """删除单条消息
    body: {scope: 'self' | 'both'}
    - self: 仅对自己隐藏（任意一方可操作）
    - both: 发送者 2 分钟内可撤回（双方都不可见）
    """
    try:
        from messaging.models import Message
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
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('删除消息错误', e)

@require_http_methods(["POST"])
@login_required
def bulk_delete_messages_api(request):
    """批量删除消息，仅在当前用户视图中隐藏。双方都删除后进入 7 天延迟物理清理队列。"""
    try:
        from messaging.models import Message
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
    except Http404:
        raise
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
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('清空对话错误', e)

