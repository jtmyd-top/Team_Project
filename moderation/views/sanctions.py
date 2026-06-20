from .common import *  # noqa: F401,F403

def _apply_sanction(target_user, sanction_type, duration, *, admin, reason, rtype, rid):
    """创建一条 UserSanction 并返回。"""
    from moderation.models import UserSanction

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
        from moderation.models import ModerationLog

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
        from moderation.models import AttachmentReport, CommentReport, MessageReport, ModerationLog, NoteReport

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
        from moderation.models import ModerationLog, UserSanction

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
