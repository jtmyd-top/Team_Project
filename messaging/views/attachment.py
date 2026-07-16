# knowledge_project/views/message/attachment.py
"""私信附件上传 / 受控访问 / 历史目录拦截"""
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from accounts.storage_quota import (
    StorageQuotaExceeded,
    ensure_storage_available,
    lock_user_storage_quota,
    quota_exceeded_payload,
)
from core.utils.request_utils import check_rate_limit_atomic
from messaging.attachment_security import inspect_message_attachment
from ._constants import (
    MESSAGE_AUDIO_MAX_SIZE,
    MESSAGE_ATTACHMENT_UPLOAD_RATE_LIMIT,
    MESSAGE_ATTACHMENT_UPLOAD_RATE_WINDOW_SECONDS,
    MESSAGE_FILE_MAX_SIZE,
    MESSAGE_FILE_MIME_TYPES,
    MESSAGE_IMAGE_MAX_SIZE,
    MESSAGE_VIDEO_MAX_SIZE,
)
from ._helpers import _attachment_payload, _serve_attachment_file

logger = logging.getLogger(__name__)


def blocked_message_attachment_media_api(request, path=None):
    return HttpResponse('私信附件只能通过受控接口访问', status=403)


@require_http_methods(["POST"])
@login_required
def upload_message_attachment_api(request):
    """上传私信附件。附件先归属于上传者，发送消息时再绑定。"""
    try:
        from messaging.models import MessageAttachment

        allowed, _count = check_rate_limit_atomic(
            f'message_attachment_upload:{request.user.id}',
            MESSAGE_ATTACHMENT_UPLOAD_RATE_LIMIT,
            MESSAGE_ATTACHMENT_UPLOAD_RATE_WINDOW_SECONDS,
        )
        if not allowed:
            return JsonResponse({'error': '附件上传过于频繁，请稍后再试'}, status=429)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'error': '没有找到上传的文件'}, status=400)

        inspection, validation_error = inspect_message_attachment(uploaded)
        if validation_error:
            return JsonResponse({'error': validation_error}, status=400)

        original_name = inspection.original_name
        mime_type = inspection.mime_type
        size = uploaded.size or 0
        is_image = inspection.attachment_type == 'image'
        is_audio = inspection.attachment_type == 'audio'
        is_video = inspection.attachment_type == 'video'

        if is_image:
            if size > MESSAGE_IMAGE_MAX_SIZE:
                return JsonResponse({'error': '图片不能超过 10MB'}, status=400)
            attachment_type = inspection.attachment_type
        elif is_audio:
            if size > MESSAGE_AUDIO_MAX_SIZE:
                return JsonResponse({'error': '语音不能超过 12MB'}, status=400)
            attachment_type = inspection.attachment_type
        elif is_video:
            if size > MESSAGE_VIDEO_MAX_SIZE:
                return JsonResponse({'error': '视频不能超过 120MB'}, status=400)
            attachment_type = inspection.attachment_type
        elif mime_type in MESSAGE_FILE_MIME_TYPES:
            if size > MESSAGE_FILE_MAX_SIZE:
                return JsonResponse({'error': '文件不能超过 25MB'}, status=400)
            attachment_type = inspection.attachment_type
        else:
            return JsonResponse({'error': '暂不支持该文件类型'}, status=400)

        try:
            with transaction.atomic():
                lock_user_storage_quota(request.user)
                ensure_storage_available(request.user, size)
                attachment = MessageAttachment.objects.create(
                    uploader=request.user,
                    file=uploaded,
                    original_name=original_name,
                    attachment_type=attachment_type,
                    mime_type=mime_type,
                    size=size,
                )
        except StorageQuotaExceeded as exc:
            return JsonResponse(quota_exceeded_payload(exc.summary), status=413)
        return JsonResponse({
            'status': 'success',
            'attachment': _attachment_payload(attachment),
        }, status=201)
    except Http404:
        raise
    except Exception as e:
        logger.error(f"上传私信附件失败: {e}", exc_info=True)
        return JsonResponse({'error': '上传失败，请稍后重试'}, status=500)


@require_http_methods(["GET"])
@login_required
def list_my_message_attachments_api(request):
    """List uploaded or currently accessible message attachments."""
    from django.core.paginator import Paginator
    from django.db.models import Q
    from messaging.attachment_access import visible_message_attachments_queryset
    from ._helpers import _attachment_payload

    def bounded_int(value, default, minimum, maximum):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return min(maximum, max(minimum, parsed))

    page = bounded_int(request.GET.get('page'), 1, 1, 1000000)
    page_size = bounded_int(request.GET.get('page_size'), 30, 1, 100)
    attachment_type = (request.GET.get('type') or '').strip()
    bound = (request.GET.get('bound') or '').strip()
    scope = (request.GET.get('scope') or 'mine').strip().lower()
    if scope not in ('mine', 'accessible'):
        return JsonResponse({'status': 'error', 'message': 'Unsupported attachment scope'}, status=400)

    qs = (
        visible_message_attachments_queryset(request.user, scope=scope)
        .select_related(
            'message',
            'message__sender',
            'message__recipient',
            'group_message',
            'group_message__group',
            'group_message__sender',
        )
        .order_by('-created_at', '-id')
    )
    if attachment_type in ('image', 'audio', 'video', 'file'):
        qs = qs.filter(attachment_type=attachment_type)
    if bound == 'sent':
        qs = qs.filter(Q(message__isnull=False) | Q(group_message__isnull=False))
    elif bound == 'draft':
        qs = qs.filter(message__isnull=True, group_message__isnull=True)

    paginator = Paginator(qs, page_size)
    current = paginator.get_page(page)
    items = []
    for attachment in current.object_list:
        payload = _attachment_payload(attachment)
        payload.update({
            'created_at': attachment.created_at.isoformat() if attachment.created_at else None,
            'was_reported': attachment.was_reported,
            'context': None,
        })
        if attachment.message_id:
            peer = (
                attachment.message.recipient
                if attachment.message.sender_id == request.user.id
                else attachment.message.sender
            )
            payload['context'] = {
                'type': 'direct',
                'message_id': attachment.message_id,
                'peer_id': peer.id,
                'peer_name': peer.username,
                'sent_at': attachment.message.created_at.isoformat() if attachment.message.created_at else None,
            }
        elif attachment.group_message_id:
            payload['context'] = {
                'type': 'group',
                'message_id': attachment.group_message_id,
                'group_id': attachment.group_message.group_id,
                'group_name': attachment.group_message.group.name,
                'sent_at': attachment.group_message.created_at.isoformat() if attachment.group_message.created_at else None,
            }
        items.append(payload)

    return JsonResponse({
        'status': 'success',
        'scope': scope,
        'attachments': items,
        'pagination': {
            'page': current.number,
            'page_size': page_size,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': current.has_next(),
            'has_previous': current.has_previous(),
        },
    })


@require_http_methods(["GET"])
@login_required
def message_attachment_file_api(request, attachment_id):
    """受控访问私信附件，仅会话双方或待发送附件上传者可访问。"""
    from messaging.models import GroupMessageDeletion, MessageAttachment, MessageGroupMember

    attachment = get_object_or_404(
        MessageAttachment.objects.select_related('message', 'group_message', 'group_message__group'),
        id=attachment_id,
    )
    message = attachment.message
    group_message = attachment.group_message
    if message is None and group_message is None:
        if attachment.uploader_id != request.user.id:
            return HttpResponse('无权访问此附件', status=403)
    elif group_message is not None:
        membership = MessageGroupMember.objects.filter(
            group=group_message.group,
            user=request.user,
            left_at__isnull=True,
        ).first()
        is_deleted_for_user = GroupMessageDeletion.objects.filter(
            message=group_message,
            user=request.user,
        ).exists()
        cleared = (
            membership is not None
            and membership.cleared_before
            and group_message.created_at <= membership.cleared_before
        )
        history_hidden = (
            membership is not None
            and membership.cleared_before is None
            and not group_message.group.allow_new_members_view_history
            and membership.joined_at
            and group_message.created_at < membership.joined_at
        )
        if not membership or group_message.is_recalled or is_deleted_for_user or history_hidden or cleared:
            return HttpResponse('无权访问此附件', status=403)
    elif request.user.id not in (message.sender_id, message.recipient_id) or not message.visible_to(request.user):
        return HttpResponse('无权访问此附件', status=403)

    return _serve_attachment_file(attachment)
