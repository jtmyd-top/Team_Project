"""Moderation common reports_meta helpers."""
from .base import *  # noqa: F401,F403

def _sanction_allowed_for_report_type(stype, rtype):
    allowed = ALLOWED_SANCTIONS_BY_REPORT_TYPE.get(rtype)
    return allowed is None or stype in allowed

def _source_report_participant_ids(rtype, rid):
    """Return user ids that belong to the source report."""
    from moderation.models import AttachmentReport, CommentReport, MessageReport, NoteReport

    if rtype == 'message':
        report = get_object_or_404(
            MessageReport.objects.select_related('reporter', 'reported_user').defer('group_message'),
            id=rid,
        )
        ids = {report.reporter_id, report.reported_user_id}
    elif rtype == 'attachment':
        report = get_object_or_404(
            AttachmentReport.objects.select_related('reporter', 'attachment__uploader'),
            id=rid,
        )
        ids = {report.reporter_id}
        if report.attachment_id:
            ids.add(report.attachment.uploader_id)
    elif rtype == 'note':
        report = get_object_or_404(NoteReport.objects.select_related('reporter', 'reported_user'), id=rid)
        ids = {report.reporter_id, report.reported_user_id}
    elif rtype == 'comment':
        report = get_object_or_404(CommentReport.objects.select_related('reporter', 'reported_user'), id=rid)
        ids = {report.reporter_id, report.reported_user_id}
    else:
        raise Http404
    ids.discard(None)
    return ids

def _report_object_key(rtype, report):
    if rtype == 'message':
        if getattr(report, 'message_id', None):
            return f'message:{report.message_id}'
        if getattr(report, 'group_message_id', None):
            return f'group_message:{report.group_message_id}'
        return f'message-report:{report.id}'
    if rtype == 'attachment':
        return f'attachment:{report.attachment_id}'
    if rtype == 'note':
        return f'note:{report.note_id}'
    if rtype == 'comment':
        return f'comment:{report.comment_id}'
    return f'{rtype}:{report.id}'

def _related_pending_reports(rtype, report):
    from moderation.models import AttachmentReport, CommentReport, MessageReport, NoteReport

    if rtype == 'message':
        qs = MessageReport.objects.filter(status='pending').defer('group_message')
        if getattr(report, 'message_id', None):
            return qs.filter(message_id=report.message_id)
        if getattr(report, 'group_message_id', None):
            return qs.filter(group_message_id=report.group_message_id)
        return qs.filter(id=report.id)
    if rtype == 'attachment':
        return AttachmentReport.objects.filter(status='pending', attachment_id=report.attachment_id)
    if rtype == 'note':
        return NoteReport.objects.filter(status='pending', note_id=report.note_id)
    if rtype == 'comment':
        return CommentReport.objects.filter(status='pending', comment_id=report.comment_id)
    return type(report).objects.none()

def _related_report_payload(r):
    return {
        'id': r.id,
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username},
        'reason': r.reason or 'other',
        'reason_display': r.get_reason_display() if hasattr(r, 'get_reason_display') else (r.reason or '其他'),
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
    }

def _report_group_meta(rtype, report):
    related = list(_related_pending_reports(rtype, report).select_related('reporter'))
    return {
        'object_key': _report_object_key(rtype, report),
        'duplicate_count': len(related),
        'reporter_names': [r.reporter.username for r in related[:5]],
    }

def _reporter_risk_summary(user):
    from moderation.models import AttachmentReport, CommentReport, MessageReport, NoteReport, UserSanction

    since = timezone.now() - timedelta(days=7)
    filed = (
        MessageReport.objects.filter(reporter=user, created_at__gte=since).count()
        + AttachmentReport.objects.filter(reporter=user, created_at__gte=since).count()
        + NoteReport.objects.filter(reporter=user, created_at__gte=since).count()
        + CommentReport.objects.filter(reporter=user, created_at__gte=since).count()
    )
    dismissed = (
        MessageReport.objects.filter(reporter=user, status='dismissed', created_at__gte=since).count()
        + AttachmentReport.objects.filter(reporter=user, status='dismissed', created_at__gte=since).count()
        + NoteReport.objects.filter(reporter=user, status='dismissed', created_at__gte=since).count()
        + CommentReport.objects.filter(reporter=user, status='dismissed', created_at__gte=since).count()
    )
    active_sanctions = UserSanction.objects.filter(user=user, is_active=True).count()
    risk_level = 'low'
    if filed >= 5 and dismissed >= 3:
        risk_level = 'high'
    elif filed >= 3 or dismissed >= 2 or active_sanctions > 0:
        risk_level = 'medium'
    return {
        'filed_7d': filed,
        'dismissed_7d': dismissed,
        'active_sanctions': active_sanctions,
        'dismissed_ratio_7d': round(dismissed / filed, 2) if filed else 0,
        'risk_level': risk_level,
    }

__all__ = [
    '_sanction_allowed_for_report_type',
    '_source_report_participant_ids',
    '_report_object_key',
    '_related_pending_reports',
    '_related_report_payload',
    '_report_group_meta',
    '_reporter_risk_summary',
]
