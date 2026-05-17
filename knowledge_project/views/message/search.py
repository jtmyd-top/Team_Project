# knowledge_project/views/message/search.py
"""全局消息搜索 / 对话导出"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ._helpers import (
    _get_avatar_url,
    _get_settings,
    _message_preview,
    _message_search_q,
    _message_search_snippet,
    _server_error_response,
    _visible_messages_qs,
)


@require_http_methods(["GET"])
@login_required
def search_messages_api(request):
    """跨会话全局搜索"""
    try:
        from ...models import Message
        q = request.GET.get('q', '').strip()
        if not q or len(q) < 2:
            return JsonResponse({'results': []})
        qs = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).exclude(is_recalled=True).filter(_message_search_q(q)).order_by('-created_at')[:40]

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
                'content_preview': _message_preview(m),
                'search_snippet': _message_search_snippet(m, q),
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
