"""Moderation common filters helpers."""
from .base import *  # noqa: F401,F403
from .reports_meta import _report_object_key

def _status_filter(qs, status, *, resolved_value):
    """跨两类工单的状态过滤。resolved_value 对应各自的“已成立处置”状态。"""
    if status in (None, '', 'all'):
        return qs
    if status == 'pending':
        return qs.filter(status='pending')
    if status == 'resolved':
        return qs.filter(status=resolved_value)
    if status == 'dismissed':
        return qs.filter(status='dismissed')
    return qs

def _date_param(value):
    if not value:
        return None
    try:
        parsed = timezone.datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    except (TypeError, ValueError):
        return None

def _apply_common_report_filters(qs, rtype, request):
    q = (request.GET.get('q') or '').strip()
    reporter = (request.GET.get('reporter') or '').strip()
    reported = (request.GET.get('reported') or request.GET.get('target') or '').strip()
    handled_by = (request.GET.get('handled_by') or '').strip()
    object_id = (request.GET.get('object_id') or '').strip()
    date_from = _date_param(request.GET.get('date_from'))
    date_to = _date_param(request.GET.get('date_to'))

    if q:
        base = Q(reporter__username__icontains=q) | Q(reason__icontains=q) | Q(detail__icontains=q)
        if rtype == 'message':
            base |= Q(reported_user__username__icontains=q) | Q(message__content__icontains=q) | Q(group_message__content__icontains=q)
        elif rtype == 'attachment':
            base |= Q(attachment__uploader__username__icontains=q) | Q(attachment__original_name__icontains=q)
        elif rtype == 'note':
            base |= Q(reported_user__username__icontains=q) | Q(note__title__icontains=q) | Q(note__content__icontains=q)
        elif rtype == 'comment':
            base |= Q(reported_user__username__icontains=q) | Q(comment__content__icontains=q) | Q(note__title__icontains=q)
        qs = qs.filter(base)
    if reporter:
        qs = qs.filter(Q(reporter_id=reporter) if reporter.isdigit() else Q(reporter__username__icontains=reporter))
    if reported:
        if rtype == 'attachment':
            qs = qs.filter(Q(attachment__uploader_id=reported) if reported.isdigit() else Q(attachment__uploader__username__icontains=reported))
        else:
            qs = qs.filter(Q(reported_user_id=reported) if reported.isdigit() else Q(reported_user__username__icontains=reported))
    if handled_by:
        qs = qs.filter(Q(handled_by_id=handled_by) if handled_by.isdigit() else Q(handled_by__username__icontains=handled_by))
    if object_id and object_id.isdigit():
        field = {'message': 'message_id', 'attachment': 'attachment_id', 'note': 'note_id', 'comment': 'comment_id'}[rtype]
        qs = qs.filter(**{field: int(object_id)})
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    return qs

def _merge_pending_items(items):
    merged = []
    seen = set()
    for kind, ts, report in items:
        key = _report_object_key(kind, report)
        merge_key = (kind, key, getattr(report, 'status', ''))
        if getattr(report, 'status', '') == 'pending' and merge_key in seen:
            continue
        if getattr(report, 'status', '') == 'pending':
            seen.add(merge_key)
        merged.append((kind, ts, report))
    return merged

__all__ = [
    '_status_filter',
    '_date_param',
    '_apply_common_report_filters',
    '_merge_pending_items',
]
