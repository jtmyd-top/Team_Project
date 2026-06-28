"""Conversation read views."""
from .common import *  # noqa: F401, F403


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

        limit, offset = _parse_message_page(request)
        messages_list, pagination = _slice_latest_page(messages_qs, limit, offset)
        unread_ids = [m.id for m in messages_list if m.sender_id == other_user.id and not m.is_read]

        # 标记接收到的消息为已读（仅对 recipient=viewer 的未读消息）
        from messaging.models import Message
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
            'pagination': pagination,
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取私信列表错误', e)
