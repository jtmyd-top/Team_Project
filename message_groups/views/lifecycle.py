from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def leave_message_group_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        if membership.role == 'owner':
            return JsonResponse({'error': '群主不能直接退出，请先解散群组'}, status=400)

        membership.left_at = timezone.now()
        membership.save(update_fields=['left_at'])
        _create_group_audit_log(group, request.user, 'group_leave', target_user=request.user)
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('退出群组错误', e)


@require_http_methods(["POST"])
@login_required
def dissolve_message_group_api(request, group_id):
    """解散群组 - 需要 2FA 验证的高危操作"""
    try:
        from messaging.models import MessageGroup
        from accounts.services import require_2fa_verified

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        if membership.role != 'owner':
            return JsonResponse({'error': '只有群主可以解散群组'}, status=403)

        # 2FA 验证逻辑
        profile = getattr(request.user, 'profile', None)
        if profile and profile.two_fa_enabled:
            from accounts.services import get_param, verify_2fa_for_request
            code = get_param(request, 'two_fa_code', '')
            use_backup = get_param(request, 'use_backup', False)

            if not code:
                return JsonResponse({
                    'status': 'require_2fa',
                    'code': 'require_2fa',
                    'message': '解散群组是高危操作，需要两步验证',
                    'method': profile.two_fa_method,
                }, status=200)

            success, message = verify_2fa_for_request(request, code, use_backup)
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'code': '2fa_failed',
                    'message': message or '验证失败',
                }, status=403)

        # 执行解散操作
        group.is_active = False
        group.updated_at = timezone.now()
        group.save(update_fields=['is_active', 'updated_at'])
        group.memberships.filter(left_at__isnull=True).update(left_at=timezone.now())
        _create_group_audit_log(group, request.user, 'group_dissolve')
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解散群组错误', e)


@require_http_methods(["POST"])
@login_required
def toggle_group_setting_api(request, group_id, action):
    try:
        from messaging.models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        data = json.loads(request.body) if request.body else {}
        now = timezone.now()
        if action == 'pin':
            value = bool(data.get('value'))
            membership.is_pinned = value
            membership.pinned_at = now if value else None
            membership.save(update_fields=['is_pinned', 'pinned_at'])
        elif action == 'mute':
            membership.is_muted = bool(data.get('value'))
            membership.save(update_fields=['is_muted'])
        elif action == 'archive':
            value = bool(data.get('value'))
            membership.is_archived = value
            membership.archived_at = now if value else None
            membership.save(update_fields=['is_archived', 'archived_at'])
        elif action == 'mark-read':
            membership.last_read_at = now
            membership.force_unread = False
            membership.save(update_fields=['last_read_at', 'force_unread'])
        elif action == 'mark-unread':
            membership.force_unread = True
            membership.save(update_fields=['force_unread'])
        elif action == 'clear':
            membership.cleared_before = now
            membership.force_unread = False
            membership.save(update_fields=['cleared_before', 'force_unread'])
        else:
            return JsonResponse({'error': '不支持的群组设置操作'}, status=400)

        return JsonResponse({'status': 'success', 'settings': _group_settings_payload(membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群组设置错误', e)
