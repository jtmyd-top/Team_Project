"""Conversation state views."""
from .common import *  # noqa: F401, F403


@require_http_methods(["POST"])
@login_required
def mark_conversation_read_api(request):
    """将对话标记为已读"""
    try:
        from messaging.models import Message
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
    except Http404:
        raise
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
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('标记未读错误', e)

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
    except Http404:
        raise
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

