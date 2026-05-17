# knowledge_project/views/message/report.py
"""附件举报 / 管理员审查 / 用户举报"""
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from ._helpers import _body_string, _serve_attachment_file, _server_error_response


@require_http_methods(["GET"])
@login_required
def review_reported_attachment(request, attachment_id):
    """仅允许管理员审查存在待处理举报工单的私信附件。"""
    from ...models import AttachmentReport, MessageAttachment

    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden('仅管理员可审查被举报附件')

    attachment = get_object_or_404(MessageAttachment.objects.select_related('message'), id=attachment_id)
    has_pending_report = AttachmentReport.objects.filter(
        attachment=attachment,
        status='pending'
    ).exists()
    if not has_pending_report:
        return HttpResponseForbidden('无查看权限或工单已结案')

    return _serve_attachment_file(attachment, disposition='inline')


@require_http_methods(["POST"])
@login_required
def report_message_attachment_api(request, attachment_id):
    """私信当事人举报指定附件，创建待处理附件举报工单。"""
    from ...models import AttachmentReport, MessageAttachment

    attachment = get_object_or_404(
        MessageAttachment.objects.select_related('message'),
        id=attachment_id
    )
    message = attachment.message
    if message is None or request.user.id not in (message.sender_id, message.recipient_id):
        return HttpResponseForbidden('只有私信参与者才能举报该附件')

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)

    reason = _body_string(data, 'reason', 'other')[:120]
    detail = _body_string(data, 'detail', '')[:1000]
    report, created = AttachmentReport.objects.get_or_create(
        attachment=attachment,
        reporter=request.user,
        status='pending',
        defaults={
            'reason': reason,
            'detail': detail,
        }
    )
    if not attachment.was_reported:
        attachment.was_reported = True
        attachment.save(update_fields=['was_reported'])
    if message and not message.was_reported:
        message.was_reported = True
        message.pending_purge_at = None
        message.save(update_fields=['was_reported', 'pending_purge_at'])

    return JsonResponse({
        'status': 'success',
        'message': '附件举报已提交，我们会尽快处理',
        'report_id': report.id,
        'created': created,
    }, status=201 if created else 200)


@require_http_methods(["POST"])
@login_required
def report_user_api(request):
    """举报用户或单条消息"""
    try:
        from ...models import Message, MessageReport
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

        if message is not None and request.user.id not in (message.sender_id, message.recipient_id):
            return JsonResponse({'error': '只有私信参与者才能举报该内容'}, status=403)

        MessageReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            message=message,
            reason=reason,
            detail=detail,
        )

        if message is not None:
            if not message.was_reported:
                message.was_reported = True
                message.pending_purge_at = None
                message.save(update_fields=['was_reported', 'pending_purge_at'])
            from ...models import AttachmentReport

            for attachment in message.attachments.all():
                if not attachment.was_reported:
                    attachment.was_reported = True
                    attachment.save(update_fields=['was_reported'])
                AttachmentReport.objects.get_or_create(
                    attachment=attachment,
                    reporter=request.user,
                    status='pending',
                    defaults={
                        'reason': reason,
                        'detail': detail,
                    }
                )

        return JsonResponse({'status': 'success', 'message': '举报已提交，我们会尽快处理'})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('举报错误', e)
