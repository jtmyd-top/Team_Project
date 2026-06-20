# knowledge_project/views/message/attachment.py
"""私信附件上传 / 受控访问 / 历史目录拦截"""
import logging
import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from ._constants import (
    MESSAGE_AUDIO_MAX_SIZE,
    MESSAGE_AUDIO_MIME_TYPES,
    MESSAGE_FILE_MAX_SIZE,
    MESSAGE_FILE_MIME_TYPES,
    MESSAGE_IMAGE_MAX_SIZE,
    MESSAGE_IMAGE_MIME_TYPES,
    MESSAGE_VIDEO_MAX_SIZE,
    MESSAGE_VIDEO_MIME_TYPES,
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
    except Http404:
        raise
    except Exception as e:
        logger.error(f"上传私信附件失败: {e}", exc_info=True)
        return JsonResponse({'error': '上传失败，请稍后重试'}, status=500)


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
        is_member = MessageGroupMember.objects.filter(
            group=group_message.group,
            user=request.user,
            left_at__isnull=True,
        ).exists()
        is_deleted_for_user = GroupMessageDeletion.objects.filter(
            message=group_message,
            user=request.user,
        ).exists()
        if not is_member or group_message.is_recalled or is_deleted_for_user:
            return HttpResponse('无权访问此附件', status=403)
    elif request.user.id not in (message.sender_id, message.recipient_id) or not message.visible_to(request.user):
        return HttpResponse('无权访问此附件', status=403)

    return _serve_attachment_file(attachment)
