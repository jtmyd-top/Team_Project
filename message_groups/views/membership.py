from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def set_group_mute_mode_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        data = json.loads(request.body or '{}')
        mute_mode = data.get('mute_mode')
        if mute_mode not in ('none', 'admins_only'):
            return JsonResponse({'error': '不支持的发言模式'}, status=400)
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        old_mode = group.mute_mode
        group.mute_mode = mute_mode
        group.updated_at = timezone.now()
        group.save(update_fields=['mute_mode', 'updated_at'])
        _create_group_audit_log(
            group,
            request.user,
            'group_mute_change',
            metadata={'old_mode': old_mode, 'mute_mode': mute_mode},
        )
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('设置群发言模式错误', e)


@require_http_methods(["POST"])
@login_required
def add_group_members_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body)
        raw_member_ids = data.get('member_ids') or []
        if not isinstance(raw_member_ids, list):
            return JsonResponse({'error': 'member_ids 必须是数组'}, status=400)

        member_ids = []
        for value in raw_member_ids:
            try:
                member_id = int(value)
            except (TypeError, ValueError):
                continue
            if member_id > 0 and member_id != request.user.id and member_id not in member_ids:
                member_ids.append(member_id)
        if not member_ids:
            return JsonResponse({'error': '请选择要加入的成员'}, status=400)

        users = list(User.objects.filter(id__in=member_ids, is_active=True))
        if len(users) != len(member_ids):
            return JsonResponse({'error': '部分用户不存在或不可用'}, status=400)
        banned_users = [user.username for user in users if _get_active_group_ban(group, user)]
        if banned_users:
            return JsonResponse({'error': f"以下用户已被本群封禁，无法加入：{', '.join(banned_users)}"}, status=403)

        with transaction.atomic():
            locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
            active_member_ids = set(
                MessageGroupMember.objects
                .select_for_update()
                .filter(group=locked_group, left_at__isnull=True)
                .values_list('user_id', flat=True)
            )
            joining_count = sum(1 for user in users if user.id not in active_member_ids)
            if len(active_member_ids) + joining_count > MAX_MESSAGE_GROUP_MEMBERS:
                return _group_full_response(locked_group, current_count=len(active_member_ids))

            for user in users:
                member, created = MessageGroupMember.objects.get_or_create(
                    group=locked_group,
                    user=user,
                    defaults={'role': 'member'},
                )
                if not created and member.left_at is not None:
                    now = timezone.now()
                    member.left_at = None
                    member.role = 'member'
                    member.joined_at = now
                    member.cleared_before = None if locked_group.allow_new_members_view_history else now
                    member.save(update_fields=['left_at', 'role', 'joined_at', 'cleared_before'])
                _create_group_audit_log(locked_group, request.user, 'member_add', target_user=user)
            locked_group.updated_at = timezone.now()
            locked_group.save(update_fields=['updated_at'])
            group = locked_group

        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('添加群成员错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def remove_group_member_api(request, group_id, user_id):
    try:
        from messaging.models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if target.role == 'owner':
            return JsonResponse({'error': '不能移除群主'}, status=400)
        if membership.role == 'admin' and target.role == 'admin':
            return JsonResponse({'error': '管理员不能移除其他管理员'}, status=403)

        target.left_at = timezone.now()
        target.save(update_fields=['left_at'])
        _create_group_audit_log(group, request.user, 'member_remove', target_user=target.user)
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('移除群成员错误', e)


@require_http_methods(["POST"])
@login_required
def set_group_member_role_api(request, group_id, user_id):
    try:
        from messaging.models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        data = json.loads(request.body or '{}')
        role = data.get('role')
        if role not in ('admin', 'member'):
            return JsonResponse({'error': '角色只能设置为管理员或成员'}, status=400)

        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if target.role == 'owner':
            return JsonResponse({'error': '不能修改群主角色'}, status=400)
        old_role = target.role
        target.role = role
        target.save(update_fields=['role'])
        _create_group_audit_log(
            group,
            request.user,
            'member_role_change',
            target_user=target.user,
            metadata={'old_role': old_role, 'role': role},
        )
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群成员角色错误', e)


@require_http_methods(["POST"])
@login_required
def mute_group_member_api(request, group_id, user_id):
    try:
        from messaging.models import MessageGroup, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body or '{}')
        target = get_object_or_404(MessageGroupMember, group=group, user_id=user_id, left_at__isnull=True)
        if not _can_manage_target(membership, target):
            return JsonResponse({'error': '无权操作该成员'}, status=403)

        if data.get('action') == 'unmute':
            target.muted_until = None
            audit_action = 'member_unmute'
        else:
            target.muted_until = _parse_mute_until(data)
            audit_action = 'member_mute'
        target.save(update_fields=['muted_until'])
        _create_group_audit_log(
            group,
            request.user,
            audit_action,
            target_user=target.user,
            metadata={'muted_until': target.muted_until.isoformat() if target.muted_until else None},
        )
        group.updated_at = timezone.now()
        group.save(update_fields=['updated_at'])
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群成员禁言错误', e)
