"""Conversation edit views."""
from .common import *  # noqa: F401, F403


@require_http_methods(["POST"])
@login_required
def edit_message_api(request, message_id):
    try:
        from messaging.models import Message

        data = json.loads(request.body)
        content = _body_string(data, 'content')
        if not content:
            return JsonResponse({'error': '消息内容不能为空'}, status=400)
        _validate_message_content(content)

        message = get_object_or_404(
            Message.objects.select_related('sender', 'recipient').prefetch_related('attachments'),
            id=message_id,
            is_recalled=False,
        )
        if message.sender_id != request.user.id:
            return JsonResponse({'error': '只能编辑自己发送的消息'}, status=403)
        if message.deleted_for_sender:
            return JsonResponse({'error': '已删除的消息不能编辑'}, status=403)

        message.content = content
        message.searchable_text = _message_searchable_text(content, message.attachments.all())
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=['content', 'searchable_text', 'is_edited', 'edited_at'])

        return JsonResponse({
            'status': 'success',
            'message': _message_payload(message, viewer=request.user),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Http404:
        raise
    except Exception as exc:
        return _server_error_response('编辑私信消息错误', exc)
