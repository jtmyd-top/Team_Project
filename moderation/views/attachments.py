from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def moderation_attachment_file_api(request, attachment_id):
    """管理员内联查看被举报附件（不受工单状态限制）。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    from messaging.models import MessageAttachment

    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    return _serve_attachment_file(attachment, disposition='inline')
