from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def moderation_reports_list_api(request):
    """举报工单列表（私信 + 附件归一化），支持 status / type 过滤与分页。"""
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    try:
        from moderation.models import AttachmentReport, CommentReport, MessageReport, NoteReport

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
        from moderation.models import AttachmentReport, CommentReport, MessageReport, ModerationLog, NoteReport

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
