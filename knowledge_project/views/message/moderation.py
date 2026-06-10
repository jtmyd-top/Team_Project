# knowledge_project/views/message/moderation.py
"""举报处置中心（仅超级管理员）

统一处置私信举报（MessageReport）与附件举报（AttachmentReport）：
- 列表 / 详情：在同一页内联展示双方资料、关联消息上下文、附件预览、
  双方既往举报与处置记录，无需跳转后台逐页查看。
- 处置：禁言私信（24h/7d/30d/永久）、封禁登录（限时/永久）、驳回（无惩罚），
  可同时惩戒恶意举报者；可选删除违规内容 / 附件；全程写处置日志可追溯。
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_http_methods

from ._helpers import (
    _get_avatar_url,
    _message_preview,
    _parse_merged_forward,
    _serve_attachment_file,
    _server_error_response,
)
from ...moderation_utils import notify_user

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
CONTEXT_WINDOW = 6  # 关联消息上下文：违规消息前后各取若干条

DURATION_MAP = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    'permanent': None,
}
DURATION_LABEL = {
    '24h': '24 小时',
    '7d': '7 天',
    '30d': '30 天',
    'permanent': '永久',
}

SANCTION_ACTION_PREFIX = {
    'mute_messages': 'mute',
    'ban_comments': 'ban_comments',
    'ban_public_notes': 'ban_public_notes',
    'ban_login': 'ban_login',
}

ALLOWED_SANCTIONS_BY_REPORT_TYPE = {
    'message': {'mute_messages', 'ban_login'},
    'attachment': {'mute_messages', 'ban_login'},
    'note': {'ban_public_notes', 'ban_login'},
    'comment': {'ban_comments', 'ban_login'},
}


def _sanction_allowed_for_report_type(stype, rtype):
    allowed = ALLOWED_SANCTIONS_BY_REPORT_TYPE.get(rtype)
    return allowed is None or stype in allowed


def _source_report_participant_ids(rtype, rid):
    """Return user ids that belong to the source report."""
    from ...models import AttachmentReport, CommentReport, MessageReport, NoteReport

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
    from ...models import AttachmentReport, CommentReport, MessageReport, NoteReport

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
    from ...models import AttachmentReport, CommentReport, MessageReport, NoteReport, UserSanction

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


def _notify_report_closed(report, rtype, decision):
    if decision == 'uphold':
        title = '举报已处理'
        body = '你的举报已被管理员确认成立。'
    else:
        title = '举报已驳回'
        body = '你的举报已由管理员审核，未被认定为违规。'
    notify_user(report.reporter, 'report_resolved', title, body, report_type=rtype, report_id=report.id, decision=decision)


def _notify_sanction_applied(sanction):
    notify_user(
        sanction.user,
        'sanction_applied',
        '账号权限已被限制',
        f'你的账号被执行了「{sanction.get_sanction_type_display()}」处置。',
        sanction_id=sanction.id,
        sanction_type=sanction.sanction_type,
        expires_at=sanction.expires_at.isoformat() if sanction.expires_at else None,
        source_report_type=sanction.source_report_type,
        source_report_id=sanction.source_report_id,
    )


# ------------------------------------------------------------------
# 权限
# ------------------------------------------------------------------
def _require_admin(request):
    """返回 None 表示放行；否则返回 403 响应。"""
    if not request.user.is_superuser:
        return HttpResponseForbidden('仅超级管理员可访问')
    return None


# ------------------------------------------------------------------
# 序列化工具
# ------------------------------------------------------------------
def _user_card(user):
    """被举报者 / 举报者的内联卡片信息（含统计、既往举报、现有制裁）。"""
    if user is None:
        return None
    from ...models import AttachmentReport, CommentReport, MessageReport, Note, NoteReport, UserSanction

    profile = getattr(user, 'profile', None)
    reports_filed = MessageReport.objects.filter(reporter=user).count()
    reports_received = (
        MessageReport.objects.filter(reported_user=user).count()
        + AttachmentReport.objects.filter(attachment__uploader=user).count()
        + NoteReport.objects.filter(reported_user=user).count()
        + CommentReport.objects.filter(reported_user=user).count()
    )
    notes_count = Note.objects.filter(author=user, is_public=True).count()

    sanctions = [
        _sanction_payload(s)
        for s in UserSanction.objects.filter(user=user, is_active=True).order_by('-created_at')
        if s.is_effective
    ]

    return {
        'id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
        'bio': (getattr(profile, 'bio', '') or '') if profile else '',
        'email': user.email or '',
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'notes_count': notes_count,
        'reports_filed': reports_filed,
        'reports_received': reports_received,
        'active_sanctions': sanctions,
    }


def _sanction_payload(s):
    pending_appeal = None
    try:
        appeal = s.appeals.filter(status='pending').order_by('-created_at').first()
        if appeal:
            pending_appeal = {
                'id': appeal.id,
                'reason': appeal.reason,
                'created_at': appeal.created_at.isoformat(),
            }
    except Exception:
        pending_appeal = None
    return {
        'id': s.id,
        'type': s.sanction_type,
        'type_display': s.get_sanction_type_display(),
        'expires_at': s.expires_at.isoformat() if s.expires_at else None,
        'is_permanent': s.is_permanent,
        'reason': s.reason or '',
        'created_at': s.created_at.isoformat(),
        'created_by': s.created_by.username if s.created_by else '',
        'pending_appeal': pending_appeal,
    }


def _attachment_brief(attachment, *, with_preview=False):
    if attachment is None:
        return None
    data = {
        'id': attachment.id,
        'type': attachment.attachment_type,
        'name': attachment.original_name,
        'mime_type': attachment.mime_type,
        'size': attachment.size,
        'was_reported': attachment.was_reported,
    }
    if with_preview:
        # 仅管理员可访问的内联预览端点
        data['preview_url'] = f'/api/moderation/attachments/{attachment.id}/file/'
    return data


def _message_context_payload(message):
    """给定违规消息，返回该会话中其前后若干条消息（管理员视角，包含已删除/已撤回）。"""
    from ...models import Message

    if message is None:
        return []
    a, b = message.sender_id, message.recipient_id
    convo = Message.objects.filter(
        Q(sender_id=a, recipient_id=b) | Q(sender_id=b, recipient_id=a)
    ).select_related('sender', 'recipient').prefetch_related('attachments').order_by('created_at')

    ids = list(convo.values_list('id', flat=True))
    try:
        idx = ids.index(message.id)
    except ValueError:
        idx = None

    if idx is None:
        window = list(convo)[-CONTEXT_WINDOW:]
    else:
        start = max(0, idx - CONTEXT_WINDOW)
        end = idx + CONTEXT_WINDOW + 1
        window = list(convo)[start:end]

    return [_context_message_payload(m, highlight_id=message.id) for m in window]


def _context_message_payload(m, highlight_id=None):
    merged_forward = _parse_merged_forward(m.content)
    return {
        'id': m.id,
        'sender': m.sender.username,
        'sender_id': m.sender_id,
        'recipient': m.recipient.username,
        'recipient_id': m.recipient_id,
        'content': m.content,
        'merged_forward': merged_forward,
        'created_at': m.created_at.isoformat(),
        'is_recalled': m.is_recalled,
        'deleted_for_sender': m.deleted_for_sender,
        'deleted_for_recipient': m.deleted_for_recipient,
        'is_highlight': (m.id == highlight_id),
        'attachments': [_attachment_brief(a, with_preview=True) for a in m.attachments.all()],
    }


# ------------------------------------------------------------------
# 工单取数
# ------------------------------------------------------------------
def _message_report_list_item(r):
    data = {
        'type': 'message',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason,
        'reason_display': r.get_reason_display(),
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)},
        'preview': (_message_preview(r.message) if r.message else '')[:80],
    }
    data.update(_report_group_meta('message', r))
    return data


def _attachment_report_list_item(r):
    uploader = r.attachment.uploader if r.attachment else None
    data = {
        'type': 'attachment',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '其他',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': uploader.id, 'username': uploader.username, 'avatar': _get_avatar_url(uploader)}
            if uploader else None
        ),
        'preview': f'[附件] {r.attachment.original_name}' if r.attachment else '[附件已删除]',
    }


def _note_report_list_item(r):
    note = r.note
    data = {
        'type': 'note',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '文章举报',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)}
            if r.reported_user else None
        ),
        'preview': f'[文章] {note.title}' if note else '[文章已删除]',
    }
    data.update(_report_group_meta('note', r))
    return data
    data.update(_report_group_meta('attachment', r))
    return data


def _comment_report_list_item(r):
    comment = r.comment
    preview = strip_tags(comment.content or '')[:80] if comment else ''
    data = {
        'type': 'comment',
        'id': r.id,
        'status': r.status,
        'status_display': r.get_status_display(),
        'reason': r.reason or 'other',
        'reason_display': r.reason or '评论举报',
        'detail': r.detail or '',
        'created_at': r.created_at.isoformat(),
        'reporter': {'id': r.reporter_id, 'username': r.reporter.username, 'avatar': _get_avatar_url(r.reporter)},
        'reported': (
            {'id': r.reported_user_id, 'username': r.reported_user.username, 'avatar': _get_avatar_url(r.reported_user)}
            if r.reported_user else None
        ),
        'preview': f'[评论] {preview}' if preview else '[评论已删除]',
    }
    data.update(_report_group_meta('comment', r))
    return data


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


# ------------------------------------------------------------------
# 页面
# ------------------------------------------------------------------
@login_required
def moderation_view(request):
    """举报处置页面，仅超级管理员可访问。"""
    if not request.user.is_superuser:
        return redirect('home')
    return render(request, 'moderation/reports.html')


# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------
@require_http_methods(["GET"])
@login_required
def moderation_reports_list_api(request):
    """举报工单列表（私信 + 附件归一化），支持 status / type 过滤与分页。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import AttachmentReport, CommentReport, MessageReport, NoteReport

        status = request.GET.get('status', 'pending')
        rtype = request.GET.get('type', 'all')
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        items = []

        if rtype in ('all', 'message'):
            mqs = _status_filter(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message').defer('group_message'),
                status, resolved_value='resolved',
            )
            mqs = _apply_common_report_filters(mqs, 'message', request)
            items.extend(('message', r.created_at, r) for r in mqs)

        if rtype in ('all', 'attachment'):
            aqs = _status_filter(
                AttachmentReport.objects.select_related('reporter', 'attachment__uploader'),
                status, resolved_value='removed',
            )
            aqs = _apply_common_report_filters(aqs, 'attachment', request)
            items.extend(('attachment', r.created_at, r) for r in aqs)

        if rtype in ('all', 'note'):
            nqs = _status_filter(
                NoteReport.objects.select_related('reporter', 'reported_user', 'note'),
                status, resolved_value='removed',
            )
            nqs = _apply_common_report_filters(nqs, 'note', request)
            items.extend(('note', r.created_at, r) for r in nqs)

        if rtype in ('all', 'comment'):
            cqs = _status_filter(
                CommentReport.objects.select_related('reporter', 'reported_user', 'comment', 'note'),
                status, resolved_value='removed',
            )
            cqs = _apply_common_report_filters(cqs, 'comment', request)
            items.extend(('comment', r.created_at, r) for r in cqs)

        items.sort(key=lambda t: t[1], reverse=True)
        if request.GET.get('merge', '1') != '0':
            items = _merge_pending_items(items)
        total = len(items)
        start = (page - 1) * PAGE_SIZE
        page_items = items[start:start + PAGE_SIZE]

        results = []
        for kind, _ts, r in page_items:
            if kind == 'message':
                results.append(_message_report_list_item(r))
            elif kind == 'attachment':
                results.append(_attachment_report_list_item(r))
            elif kind == 'note':
                results.append(_note_report_list_item(r))
            else:
                results.append(_comment_report_list_item(r))

        # 待处理总数（角标用）
        pending_count = (
            MessageReport.objects.filter(status='pending').count()
            + AttachmentReport.objects.filter(status='pending').count()
            + NoteReport.objects.filter(status='pending').count()
            + CommentReport.objects.filter(status='pending').count()
        )

        return JsonResponse({
            'status': 'success',
            'results': results,
            'total': total,
            'page': page,
            'page_size': PAGE_SIZE,
            'has_more': start + PAGE_SIZE < total,
            'pending_count': pending_count,
        })
    except Exception as e:
        return _server_error_response('获取举报列表错误', e)


@require_http_methods(["GET"])
@login_required
def moderation_report_detail_api(request, rtype, rid):
    """单工单完整详情：双方资料卡 + 关联消息上下文 / 附件预览 + 处置历史。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import AttachmentReport, CommentReport, MessageReport, ModerationLog, NoteReport

        if rtype == 'message':
            r = get_object_or_404(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message', 'handled_by').defer('group_message'),
                id=rid,
            )
            reported_user = r.reported_user
            base = {
                'type': 'message',
                'id': r.id,
                'status': r.status,
                'status_display': r.get_status_display(),
                'reason': r.reason,
                'reason_display': r.get_reason_display(),
                'detail': r.detail or '',
                'created_at': r.created_at.isoformat(),
                'resolution_note': r.resolution_note or '',
                'handled_by': r.handled_by.username if r.handled_by else '',
                'resolved_at': r.resolved_at.isoformat() if r.resolved_at else None,
                'message_context': _message_context_payload(r.message),
                'attachment': None,
            }
        elif rtype == 'attachment':
            r = get_object_or_404(
                AttachmentReport.objects.select_related('reporter', 'attachment__uploader', 'attachment__message', 'handled_by'),
                id=rid,
            )
            reported_user = r.attachment.uploader if r.attachment else None
            base = {
                'type': 'attachment',
                'id': r.id,
                'status': r.status,
                'status_display': r.get_status_display(),
                'reason': r.reason or 'other',
                'reason_display': r.reason or '其他',
                'detail': r.detail or '',
                'created_at': r.created_at.isoformat(),
                'resolution_note': r.resolution_note or '',
                'handled_by': r.handled_by.username if r.handled_by else '',
                'resolved_at': r.handled_at.isoformat() if r.handled_at else None,
                'message_context': _message_context_payload(r.attachment.message) if r.attachment else [],
                'attachment': _attachment_brief(r.attachment, with_preview=True),
            }
        elif rtype == 'note':
            r = get_object_or_404(
                NoteReport.objects.select_related('reporter', 'reported_user', 'note', 'handled_by'),
                id=rid,
            )
            reported_user = r.reported_user
            note = r.note
            base = {
                'type': 'note',
                'id': r.id,
                'status': r.status,
                'status_display': r.get_status_display(),
                'reason': r.reason or 'other',
                'reason_display': r.reason or '文章举报',
                'detail': r.detail or '',
                'created_at': r.created_at.isoformat(),
                'resolution_note': r.resolution_note or '',
                'handled_by': r.handled_by.username if r.handled_by else '',
                'resolved_at': r.handled_at.isoformat() if r.handled_at else None,
                'message_context': [],
                'attachment': None,
                'note': {
                    'id': note.id,
                    'title': note.title,
                    'is_public': note.is_public,
                    'public_url': f'/notes/public/{note.public_id}/' if note.public_id else '',
                    'content_preview': strip_tags(note.content or '')[:300],
                } if note else None,
            }
        elif rtype == 'comment':
            r = get_object_or_404(
                CommentReport.objects.select_related('reporter', 'reported_user', 'comment', 'note', 'handled_by'),
                id=rid,
            )
            reported_user = r.reported_user
            comment = r.comment
            note = r.note or (comment.note if comment else None)
            base = {
                'type': 'comment',
                'id': r.id,
                'status': r.status,
                'status_display': r.get_status_display(),
                'reason': r.reason or 'other',
                'reason_display': r.reason or '评论举报',
                'detail': r.detail or '',
                'created_at': r.created_at.isoformat(),
                'resolution_note': r.resolution_note or '',
                'handled_by': r.handled_by.username if r.handled_by else '',
                'resolved_at': r.handled_at.isoformat() if r.handled_at else None,
                'message_context': [],
                'attachment': None,
                'note': {
                    'id': note.id,
                    'title': note.title,
                    'is_public': note.is_public,
                    'public_url': f'/notes/public/{note.public_id}/' if note.public_id else '',
                } if note else None,
                'comment': {
                    'id': comment.id,
                    'author': comment.author.username,
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat(),
                } if comment else None,
            }
        else:
            raise Http404

        logs = ModerationLog.objects.filter(report_type=rtype, report_id=rid).select_related('moderator', 'target_user')
        base['logs'] = [{
            'action': l.action,
            'moderator': l.moderator.username if l.moderator else '',
            'target_user': l.target_user.username if l.target_user else '',
            'note': l.note or '',
            'created_at': l.created_at.isoformat(),
        } for l in logs]

        related = list(_related_pending_reports(rtype, r).select_related('reporter'))
        base['evidence_snapshot'] = r.evidence_snapshot or {}
        base['object_key'] = _report_object_key(rtype, r)
        base['related_reports'] = [_related_report_payload(item) for item in related]
        base['duplicate_count'] = len(related)
        base['reporter_risk'] = _reporter_risk_summary(r.reporter)
        base['reporter'] = _user_card(r.reporter)
        base['reported'] = _user_card(reported_user)

        return JsonResponse({'status': 'success', 'report': base})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取举报详情错误', e)


def _apply_sanction(target_user, sanction_type, duration, *, admin, reason, rtype, rid):
    """创建一条 UserSanction 并返回。"""
    from ...models import UserSanction

    if duration not in DURATION_MAP:
        raise ValueError('无效的处置时长')
    delta = DURATION_MAP[duration]
    expires_at = None if delta is None else timezone.now() + delta
    sanction = UserSanction.objects.create(
        user=target_user,
        sanction_type=sanction_type,
        expires_at=expires_at,
        reason=reason,
        created_by=admin,
        source_report_type=rtype,
        source_report_id=rid,
    )
    # 永久封禁登录：同步停用账户，与既有 is_active 逻辑兼容
    if sanction_type == 'ban_login' and expires_at is None and target_user.is_active:
        target_user.is_active = False
        target_user.save(update_fields=['is_active'])
    _notify_sanction_applied(sanction)
    return sanction


@require_http_methods(["POST"])
@login_required
def moderation_user_sanction_api(request, user_id):
    """Allow a superuser to sanction a user without requiring a new pending report."""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import ModerationLog

        data = json.loads(request.body) if request.body else {}
        stype = data.get('type')
        duration = data.get('duration')
        note = (data.get('note') or '').strip()[:2000]
        source_rtype = data.get('source_report_type') or ''
        source_rid = data.get('source_report_id')

        if stype not in SANCTION_ACTION_PREFIX:
            return JsonResponse({'error': '无效的处置类型'}, status=400)
        if duration not in DURATION_MAP:
            return JsonResponse({'error': '无效的处置时长'}, status=400)
        if source_rtype not in ('message', 'attachment', 'note', 'comment'):
            return JsonResponse({'error': '无效的来源工单类型'}, status=400)
        if not _sanction_allowed_for_report_type(stype, source_rtype):
            return JsonResponse({'error': '该举报类型不允许执行此处置'}, status=400)
        try:
            source_rid = int(source_rid) if source_rid not in (None, '') else None
        except (TypeError, ValueError):
            return JsonResponse({'error': '无效的来源工单 ID'}, status=400)
        if source_rid is None:
            return JsonResponse({'error': '重新处置必须绑定来源工单'}, status=400)

        target_user = get_object_or_404(User, id=user_id)
        if target_user.id not in _source_report_participant_ids(source_rtype, source_rid):
            return JsonResponse({'error': '被处置用户不属于来源工单'}, status=400)
        log_rtype = source_rtype
        log_rid = source_rid

        with transaction.atomic():
            sanction = _apply_sanction(
                target_user,
                stype,
                duration,
                admin=request.user,
                reason=note,
                rtype=source_rtype,
                rid=source_rid,
            )
            base_action = f'{SANCTION_ACTION_PREFIX[stype]}_{duration}'
            ModerationLog.objects.create(
                report_type=log_rtype,
                report_id=log_rid,
                moderator=request.user,
                target_user=target_user,
                action=f'manual:{base_action}',
                note=note,
            )

        return JsonResponse({
            'status': 'success',
            'message': '用户已重新处置',
            'sanction': _sanction_payload(sanction),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('重新处置用户错误', e)


@require_http_methods(["POST"])
@login_required
def moderation_resolve_api(request, rtype, rid):
    """执行处置：施加制裁 / 删除违规内容 / 更新工单状态 / 写处置日志。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import AttachmentReport, CommentReport, MessageReport, ModerationLog, NoteReport

        data = json.loads(request.body) if request.body else {}
        decision = data.get('decision', 'uphold')  # uphold | dismiss
        if decision not in ('uphold', 'dismiss'):
            return JsonResponse({'error': '无效的处置决定'}, status=400)
        sanctions = data.get('sanctions') or []
        if not isinstance(sanctions, list):
            return JsonResponse({'error': 'sanctions 必须是数组'}, status=400)
        remove_content = bool(data.get('remove_content'))
        resolve_related = data.get('resolve_related', True) is not False
        note = (data.get('note') or '').strip()[:2000]
        admin = request.user

        # 取工单 + 解析双方
        if rtype == 'message':
            report = get_object_or_404(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message').defer('group_message'), id=rid
            )
            if report.status != 'pending':
                return JsonResponse({'error': '该举报工单已处理，不能重复处置'}, status=400)
            reported_user = report.reported_user
            reporter = report.reporter
            target_message = report.message
            target_attachment = None
            target_note = None
            target_comment = None
        elif rtype == 'attachment':
            report = get_object_or_404(
                AttachmentReport.objects.select_related('reporter', 'attachment__uploader', 'attachment__message'), id=rid
            )
            if report.status != 'pending':
                return JsonResponse({'error': '该举报工单已处理，不能重复处置'}, status=400)
            reported_user = report.attachment.uploader if report.attachment else None
            reporter = report.reporter
            target_message = report.attachment.message if report.attachment else None
            target_attachment = report.attachment
            target_note = None
            target_comment = None
        elif rtype == 'note':
            report = get_object_or_404(
                NoteReport.objects.select_related('reporter', 'reported_user', 'note'), id=rid
            )
            if report.status != 'pending':
                return JsonResponse({'error': '该举报工单已处理，不能重复处置'}, status=400)
            reported_user = report.reported_user
            reporter = report.reporter
            target_message = None
            target_attachment = None
            target_note = report.note
            target_comment = None
        elif rtype == 'comment':
            report = get_object_or_404(
                CommentReport.objects.select_related('reporter', 'reported_user', 'comment', 'note'), id=rid
            )
            if report.status != 'pending':
                return JsonResponse({'error': '该举报工单已处理，不能重复处置'}, status=400)
            reported_user = report.reported_user
            reporter = report.reporter
            target_message = None
            target_attachment = None
            target_note = report.note
            target_comment = report.comment
        else:
            raise Http404

        for item in sanctions:
            target_key = item.get('target')
            stype = item.get('type')
            duration = item.get('duration')
            if target_key not in ('reported', 'reporter'):
                return JsonResponse({'error': '无效的处置对象'}, status=400)
            if stype not in SANCTION_ACTION_PREFIX:
                return JsonResponse({'error': '无效的处置类型'}, status=400)
            if duration not in DURATION_MAP:
                return JsonResponse({'error': '无效的处置时长'}, status=400)
            if not _sanction_allowed_for_report_type(stype, rtype):
                return JsonResponse({'error': '该举报类型不允许执行此处置'}, status=400)

        related_report_ids = list(
            _related_pending_reports(rtype, report).exclude(id=report.id).values_list('id', flat=True)
        )

        with transaction.atomic():
            applied = []
            for item in sanctions:
                target_key = item.get('target')
                stype = item.get('type')
                duration = item.get('duration')
                if target_key == 'reported':
                    target_user = reported_user
                elif target_key == 'reporter':
                    target_user = reporter
                else:
                    raise ValueError('无效的处置对象')
                if target_user is None:
                    raise ValueError('处置对象不存在')

                sanction = _apply_sanction(
                    target_user, stype, duration,
                    admin=admin, reason=note, rtype=rtype, rid=rid,
                )
                applied.append((target_user, stype, duration))

                action = f'{SANCTION_ACTION_PREFIX[stype]}_{duration}'
                if target_key == 'reporter':
                    action = f'penalize_reporter:{action}'
                ModerationLog.objects.create(
                    report_type=rtype, report_id=rid, moderator=admin,
                    target_user=target_user, action=action, note=note,
                )

            # 删除违规内容
            if remove_content:
                if target_attachment is not None:
                    # 只删物理文件并清空字段，保留附件行与举报工单（附件 FK 为 CASCADE，
                    # 删除附件行会级联删掉本工单，破坏审计记录）
                    if target_attachment.file:
                        try:
                            target_attachment.file.delete(save=False)
                        except Exception as exc:
                            logger.warning("删除被举报附件文件失败: attachment=%s, error=%s",
                                           target_attachment.id, exc, exc_info=True)
                        target_attachment.file = ''
                        target_attachment.save(update_fields=['file'])
                elif target_message is not None:
                    target_message.is_recalled = True
                    target_message.recalled_at = timezone.now()
                    target_message.save(update_fields=['is_recalled', 'recalled_at'])
                elif target_comment is not None:
                    target_comment.delete()
                    if rtype == 'comment':
                        report.comment = None
                elif target_note is not None:
                    if target_note.is_public:
                        target_note.is_public = False
                        target_note.save(update_fields=['is_public'])
                ModerationLog.objects.create(
                    report_type=rtype, report_id=rid, moderator=admin,
                    target_user=reported_user, action='remove_content', note=note,
                )

            # 更新工单状态
            now = timezone.now()
            if rtype == 'message':
                report.status = 'resolved' if decision == 'uphold' else 'dismissed'
                report.handled_by = admin
                report.resolution_note = note
                report.resolved_at = now
                report.save(update_fields=['status', 'handled_by', 'resolution_note', 'resolved_at'])
            else:
                report.status = 'removed' if decision == 'uphold' else 'dismissed'
                report.handled_by = admin
                report.resolution_note = note
                report.handled_at = now
                report.save()

            merged_count = 0
            _notify_report_closed(report, rtype, decision)
            if resolve_related:
                related_qs = type(report).objects.filter(id__in=related_report_ids, status='pending').select_related('reporter')
                if rtype == 'message':
                    related_qs = related_qs.defer('group_message')
                for related in related_qs:
                    if rtype == 'message':
                        related.status = 'resolved' if decision == 'uphold' else 'dismissed'
                        related.handled_by = admin
                        related.resolution_note = note
                        related.resolved_at = now
                        related.save(update_fields=['status', 'handled_by', 'resolution_note', 'resolved_at'])
                    else:
                        related.status = 'removed' if decision == 'uphold' else 'dismissed'
                        related.handled_by = admin
                        related.resolution_note = note
                        related.handled_at = now
                        related.save(update_fields=['status', 'handled_by', 'resolution_note', 'handled_at', 'pending_dedup_key'])
                    ModerationLog.objects.create(
                        report_type=rtype,
                        report_id=related.id,
                        moderator=admin,
                        target_user=reported_user,
                        action='merged_resolve' if decision == 'uphold' else 'merged_dismiss',
                        note=note,
                    )
                    _notify_report_closed(related, rtype, decision)
                    merged_count += 1

            if not applied and not remove_content:
                ModerationLog.objects.create(
                    report_type=rtype, report_id=rid, moderator=admin,
                    target_user=reported_user,
                    action='no_action' if decision == 'uphold' else 'dismiss',
                    note=note,
                )

        return JsonResponse({'status': 'success', 'message': '处置已提交', 'merged_count': merged_count})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处置错误', e)


@require_http_methods(["POST"])
@login_required
def moderation_revoke_sanction_api(request, sid):
    """提前解除某条制裁。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import ModerationLog, UserSanction

        sanction = get_object_or_404(UserSanction, id=sid)
        if sanction.is_active:
            sanction.is_active = False
            sanction.revoked_at = timezone.now()
            sanction.save(update_fields=['is_active', 'revoked_at'])
            # 永久封禁登录解除时恢复账户
            if sanction.sanction_type == 'ban_login' and not sanction.user.is_active:
                sanction.user.is_active = True
                sanction.user.save(update_fields=['is_active'])
            ModerationLog.objects.create(
                report_type=sanction.source_report_type or 'message',
                report_id=sanction.source_report_id or 0,
                moderator=request.user, target_user=sanction.user,
                action=f'revoke:{sanction.sanction_type}',
                note=f'解除制裁 #{sanction.id}',
            )
            notify_user(
                sanction.user,
                'sanction_revoked',
                '账号限制已解除',
                f'你的「{sanction.get_sanction_type_display()}」处置已被管理员解除。',
                sanction_id=sanction.id,
                sanction_type=sanction.sanction_type,
            )
        return JsonResponse({'status': 'success', 'message': '制裁已解除'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解除制裁错误', e)


@require_http_methods(["GET"])
@login_required
def moderation_templates_api(request):
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import ModerationTemplate

        rtype = request.GET.get('type') or ''
        decision = request.GET.get('decision') or ''
        qs = ModerationTemplate.objects.filter(is_active=True)
        if rtype:
            qs = qs.filter(Q(report_type='') | Q(report_type=rtype))
        if decision:
            qs = qs.filter(Q(decision='') | Q(decision=decision))
        return JsonResponse({
            'status': 'success',
            'templates': [
                {
                    'id': t.id,
                    'title': t.title,
                    'report_type': t.report_type,
                    'decision': t.decision,
                    'content': t.content,
                }
                for t in qs[:100]
            ],
        })
    except Exception as e:
        return _server_error_response('获取处置模板错误', e)


@require_http_methods(["POST"])
@login_required
def moderation_sanction_appeal_api(request, sid):
    try:
        from ...models import ModerationAppeal, UserSanction

        sanction = get_object_or_404(UserSanction, id=sid, user=request.user)
        if not sanction.is_effective:
            return JsonResponse({'error': '该处置已失效，不能申诉'}, status=400)
        data = json.loads(request.body) if request.body else {}
        reason = (data.get('reason') or '').strip()[:2000]
        if len(reason) < 5:
            return JsonResponse({'error': '请填写申诉理由'}, status=400)
        appeal, created = ModerationAppeal.objects.get_or_create(
            sanction=sanction,
            user=request.user,
            status='pending',
            defaults={'reason': reason},
        )
        if not created and reason != appeal.reason:
            appeal.reason = reason
            appeal.save(update_fields=['reason'])
        notify_user(
            request.user,
            'appeal_submitted',
            '申诉已提交',
            '你的处置申诉已提交，管理员会尽快处理。',
            sanction_id=sanction.id,
            appeal_id=appeal.id,
        )
        return JsonResponse({'status': 'success', 'appeal_id': appeal.id, 'created': created})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('提交申诉错误', e)


@require_http_methods(["POST"])
@login_required
def moderation_appeal_resolve_api(request, appeal_id):
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import ModerationAppeal, ModerationLog

        appeal = get_object_or_404(ModerationAppeal.objects.select_related('sanction', 'user'), id=appeal_id)
        if appeal.status != 'pending':
            return JsonResponse({'error': '该申诉已处理'}, status=400)
        data = json.loads(request.body) if request.body else {}
        decision = data.get('decision')
        note = (data.get('note') or '').strip()[:2000]
        if decision not in ('accepted', 'rejected'):
            return JsonResponse({'error': '无效的申诉处理结果'}, status=400)

        with transaction.atomic():
            appeal.status = decision
            appeal.handled_by = request.user
            appeal.resolution_note = note
            appeal.handled_at = timezone.now()
            appeal.save(update_fields=['status', 'handled_by', 'resolution_note', 'handled_at'])
            if decision == 'accepted' and appeal.sanction.is_active:
                appeal.sanction.is_active = False
                appeal.sanction.revoked_at = timezone.now()
                appeal.sanction.save(update_fields=['is_active', 'revoked_at'])
                if appeal.sanction.sanction_type == 'ban_login' and not appeal.user.is_active:
                    appeal.user.is_active = True
                    appeal.user.save(update_fields=['is_active'])
            ModerationLog.objects.create(
                report_type=appeal.sanction.source_report_type or 'message',
                report_id=appeal.sanction.source_report_id or 0,
                moderator=request.user,
                target_user=appeal.user,
                action=f'appeal:{decision}',
                note=note,
            )
        notify_user(
            appeal.user,
            'appeal_resolved',
            '申诉已处理',
            '你的申诉已通过，相关处置已解除。' if decision == 'accepted' else '你的申诉已被管理员驳回。',
            appeal_id=appeal.id,
            sanction_id=appeal.sanction_id,
            decision=decision,
        )
        return JsonResponse({'status': 'success', 'decision': decision})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理申诉错误', e)


@require_http_methods(["GET"])
@login_required
def moderation_attachment_file_api(request, attachment_id):
    """管理员内联查看被举报附件（不受工单状态限制）。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    from ...models import MessageAttachment

    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    return _serve_attachment_file(attachment, disposition='inline')
