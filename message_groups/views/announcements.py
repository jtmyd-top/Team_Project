from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def _legacy_update_group_announcement_api(request, group_id):
    """更新群公告"""
    try:
        from messaging.models import MessageGroup, MessageGroupAnnouncementHistory, MessageGroupAnnouncementRead, MessageGroupAuditLog

        data = json.loads(request.body)
        announcement = data.get('announcement', '').strip()
        pin = data.get('pin', False)  # 是否置顶

        if len(announcement) > 2000:
            return JsonResponse({'error': '群公告不能超过2000字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以修改公告
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        with transaction.atomic():
            group.announcement = announcement
            group.announcement_updated_by = request.user
            if pin:
                group.announcement_pinned_at = timezone.now()
            else:
                group.announcement_pinned_at = None
            group.save(update_fields=['announcement', 'announcement_updated_by', 'announcement_pinned_at', 'updated_at'])
            history = MessageGroupAnnouncementHistory.objects.create(
                group=group,
                editor=request.user,
                content=announcement,
                pinned=bool(pin),
            )
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=history,
                defaults={'read_at': timezone.now()},
            )

            # 记录审计日志
            MessageGroupAuditLog.objects.create(
                group=group,
                actor=request.user,
                action='group_announcement_update',
                metadata={'pinned': pin}
            )

        # 发送通知（在事务外执行，避免阻塞）
        if announcement:  # 只有非空公告才发送通知
            try:
                _notify_announcement_everyone(group, request.user, announcement)
            except Exception as e:
                logger.error(f'群公告通知发送失败: {e}', exc_info=True)
                # 不影响公告保存成功的响应

        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'announcement': announcement,
            'pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
            'read_stats': _announcement_read_payload(group, history),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群公告错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def _legacy_group_announcement_reads_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupAnnouncementRead

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        announcement = group.announcement_history.order_by('-created_at').first()
        if request.method == "POST" and announcement:
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=announcement,
                defaults={'read_at': timezone.now()},
            )

        return JsonResponse({
            'status': 'success',
            'read_stats': _announcement_read_payload(group, announcement),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('Group announcement read status error', e)


# Announcement v2 APIs.
def _require_group_announcement_manager(group, user):
    membership, error = _require_group_member(group, user)
    if error is not None:
        return None, error
    if membership.role not in ['owner', 'admin']:
        return membership, JsonResponse({'error': '权限不足'}, status=403)
    return membership, None


def _update_announcement_message(message, content):
    if not message or message.is_recalled:
        return
    now = timezone.now()
    message.content = _announcement_message_content(content)
    message.searchable_text = _message_searchable_text(message.content)
    message.is_edited = True
    message.edited_at = now
    message.save(update_fields=['content', 'searchable_text', 'is_edited', 'edited_at'])


@require_http_methods(["POST"])
@login_required
def update_group_announcement_api(request, group_id):
    """Create a group announcement and send the linked @all group message."""
    try:
        from messaging.models import GroupMessage, MessageGroup, MessageGroupAnnouncementHistory, MessageGroupAnnouncementRead

        data = json.loads(request.body or '{}')
        announcement = (data.get('announcement') or '').strip()
        pin = bool(data.get('pin', False))
        if not announcement:
            return JsonResponse({'error': '群公告不能为空'}, status=400)
        if len(announcement) > 2000:
            return JsonResponse({'error': '群公告不能超过 2000 字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_announcement_manager(group, request.user)
        if error is not None:
            return error

        with transaction.atomic():
            message_content = _announcement_message_content(announcement)
            message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=message_content,
                searchable_text=_message_searchable_text(message_content),
            )
            history = MessageGroupAnnouncementHistory.objects.create(
                group=group,
                editor=request.user,
                content=announcement,
                pinned=pin,
                message=message,
            )
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=history,
                defaults={'read_at': timezone.now()},
            )
            _sync_group_announcement_summary(group)
            group.updated_at = timezone.now()
            group.save(update_fields=[
                'announcement',
                'announcement_updated_by',
                'announcement_pinned_at',
                'updated_at',
            ])
            _create_group_audit_log(
                group,
                request.user,
                'group_announcement_update',
                metadata={'pinned': pin, 'operation': 'create', 'announcement_id': history.id},
            )

        try:
            _notify_announcement_everyone(group, request.user, announcement, message=message)
        except Exception as exc:
            logger.error('Group announcement notification failed: %s', exc, exc_info=True)

        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'announcement': announcement,
            'pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
            'read_stats': _announcement_read_payload(group, history),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('Update group announcement error', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def group_announcement_detail_api(request, group_id, announcement_id):
    """Edit, pin/unpin, or delete one group announcement."""
    try:
        from messaging.models import MessageGroup, MessageGroupAnnouncementHistory, MessageGroupAnnouncementRead

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_announcement_manager(group, request.user)
        if error is not None:
            return error
        history = get_object_or_404(
            MessageGroupAnnouncementHistory.objects.select_related('message'),
            id=announcement_id,
            group=group,
            deleted_at__isnull=True,
        )

        with transaction.atomic():
            if request.method == "DELETE":
                history.deleted_at = timezone.now()
                history.editor = request.user
                history.pinned = False
                history.save(update_fields=['deleted_at', 'editor', 'pinned', 'updated_at'])
                if history.message and not history.message.is_recalled:
                    history.message.is_recalled = True
                    history.message.recalled_at = timezone.now()
                    history.message.save(update_fields=['is_recalled', 'recalled_at'])
                operation = 'delete'
            else:
                data = json.loads(request.body or '{}')
                announcement = (data.get('announcement') or '').strip()
                pin = bool(data.get('pin', False))
                if not announcement:
                    return JsonResponse({'error': '群公告不能为空'}, status=400)
                if len(announcement) > 2000:
                    return JsonResponse({'error': '群公告不能超过 2000 字'}, status=400)
                history.content = announcement
                history.pinned = pin
                history.editor = request.user
                history.save(update_fields=['content', 'pinned', 'editor', 'updated_at'])
                _update_announcement_message(history.message, announcement)
                MessageGroupAnnouncementRead.objects.update_or_create(
                    group=group,
                    user=request.user,
                    announcement=history,
                    defaults={'read_at': timezone.now()},
                )
                operation = 'update'

            latest = _sync_group_announcement_summary(group)
            group.updated_at = timezone.now()
            group.save(update_fields=[
                'announcement',
                'announcement_updated_by',
                'announcement_pinned_at',
                'updated_at',
            ])
            _create_group_audit_log(
                group,
                request.user,
                'group_announcement_update',
                metadata={'pinned': history.pinned, 'operation': operation, 'announcement_id': history.id},
            )

        return JsonResponse({
            'status': 'success',
            'group': _group_detail_payload(group, membership),
            'announcement': latest.content if latest else '',
            'pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
            'read_stats': _announcement_read_payload(group, latest),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('Group announcement detail error', e)


@require_http_methods(["GET", "POST"])
@login_required
def group_announcement_reads_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupAnnouncementRead

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        announcement = _latest_active_announcement(group)
        if request.method == "POST" and announcement:
            MessageGroupAnnouncementRead.objects.update_or_create(
                group=group,
                user=request.user,
                announcement=announcement,
                defaults={'read_at': timezone.now()},
            )

        return JsonResponse({
            'status': 'success',
            'read_stats': _announcement_read_payload(group, announcement),
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('Group announcement read status error', e)
