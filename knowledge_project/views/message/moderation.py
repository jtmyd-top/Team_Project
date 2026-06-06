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
    from ...models import MessageReport, AttachmentReport, Note, UserSanction

    profile = getattr(user, 'profile', None)
    reports_filed = MessageReport.objects.filter(reporter=user).count()
    reports_received = (
        MessageReport.objects.filter(reported_user=user).count()
        + AttachmentReport.objects.filter(attachment__uploader=user).count()
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
    return {
        'id': s.id,
        'type': s.sanction_type,
        'type_display': s.get_sanction_type_display(),
        'expires_at': s.expires_at.isoformat() if s.expires_at else None,
        'is_permanent': s.is_permanent,
        'reason': s.reason or '',
        'created_at': s.created_at.isoformat(),
        'created_by': s.created_by.username if s.created_by else '',
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
    return {
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


def _attachment_report_list_item(r):
    uploader = r.attachment.uploader if r.attachment else None
    return {
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
        from ...models import MessageReport, AttachmentReport

        status = request.GET.get('status', 'pending')
        rtype = request.GET.get('type', 'all')
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        items = []

        if rtype in ('all', 'message'):
            mqs = _status_filter(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message'),
                status, resolved_value='resolved',
            )
            items.extend(('message', r.created_at, r) for r in mqs)

        if rtype in ('all', 'attachment'):
            aqs = _status_filter(
                AttachmentReport.objects.select_related('reporter', 'attachment__uploader'),
                status, resolved_value='removed',
            )
            items.extend(('attachment', r.created_at, r) for r in aqs)

        items.sort(key=lambda t: t[1], reverse=True)
        total = len(items)
        start = (page - 1) * PAGE_SIZE
        page_items = items[start:start + PAGE_SIZE]

        results = []
        for kind, _ts, r in page_items:
            if kind == 'message':
                results.append(_message_report_list_item(r))
            else:
                results.append(_attachment_report_list_item(r))

        # 待处理总数（角标用）
        pending_count = (
            MessageReport.objects.filter(status='pending').count()
            + AttachmentReport.objects.filter(status='pending').count()
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
        from ...models import MessageReport, AttachmentReport, ModerationLog

        if rtype == 'message':
            r = get_object_or_404(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message', 'handled_by'),
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
    return sanction


@require_http_methods(["POST"])
@login_required
def moderation_resolve_api(request, rtype, rid):
    """执行处置：施加制裁 / 删除违规内容 / 更新工单状态 / 写处置日志。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from ...models import MessageReport, AttachmentReport, ModerationLog

        data = json.loads(request.body) if request.body else {}
        decision = data.get('decision', 'uphold')  # uphold | dismiss
        if decision not in ('uphold', 'dismiss'):
            return JsonResponse({'error': '无效的处置决定'}, status=400)
        sanctions = data.get('sanctions') or []
        if not isinstance(sanctions, list):
            return JsonResponse({'error': 'sanctions 必须是数组'}, status=400)
        remove_content = bool(data.get('remove_content'))
        note = (data.get('note') or '').strip()[:2000]
        admin = request.user

        # 取工单 + 解析双方
        if rtype == 'message':
            report = get_object_or_404(
                MessageReport.objects.select_related('reporter', 'reported_user', 'message'), id=rid
            )
            if report.status != 'pending':
                return JsonResponse({'error': '该举报工单已处理，不能重复处置'}, status=400)
            reported_user = report.reported_user
            reporter = report.reporter
            target_message = report.message
            target_attachment = None
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
        else:
            raise Http404

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
                if stype not in ('mute_messages', 'ban_login'):
                    raise ValueError('无效的处置类型')

                sanction = _apply_sanction(
                    target_user, stype, duration,
                    admin=admin, reason=note, rtype=rtype, rid=rid,
                )
                applied.append((target_user, stype, duration))

                action = (
                    f'mute_{duration}' if stype == 'mute_messages' else f'ban_login_{duration}'
                )
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

            if not applied and not remove_content:
                ModerationLog.objects.create(
                    report_type=rtype, report_id=rid, moderator=admin,
                    target_user=reported_user,
                    action='no_action' if decision == 'uphold' else 'dismiss',
                    note=note,
                )

        return JsonResponse({'status': 'success', 'message': '处置已提交'})
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
        return JsonResponse({'status': 'success', 'message': '制裁已解除'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解除制裁错误', e)


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
