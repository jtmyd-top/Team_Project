from .common import *  # noqa: F401,F403

@require_http_methods(["GET", "POST"])
@login_required
def group_invite_links_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupInviteLink
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.method == 'POST':
            data = json.loads(request.body or '{}')
            expires_at = None
            expires_in_minutes = data.get('expires_in_minutes')
            if expires_in_minutes not in (None, '', 0, '0'):
                try:
                    minutes = int(expires_in_minutes)
                except (TypeError, ValueError):
                    return JsonResponse({'error': '过期时间必须是分钟数'}, status=400)
                if minutes < 1:
                    return JsonResponse({'error': '过期时间必须大于 0'}, status=400)
                expires_at = timezone.now() + timedelta(minutes=min(minutes, 60 * 24 * 30))

            max_uses = data.get('max_uses')
            if max_uses in ('', 0, '0'):
                max_uses = None
            elif max_uses is not None:
                try:
                    max_uses = int(max_uses)
                except (TypeError, ValueError):
                    return JsonResponse({'error': '使用次数必须是数字'}, status=400)
                if max_uses < 1:
                    return JsonResponse({'error': '使用次数必须大于 0'}, status=400)
                max_uses = min(max_uses, 1000)

            with transaction.atomic():
                locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
                if MessageGroupInviteLink.objects.filter(group=locked_group).exists():
                    return JsonResponse({'error': '每个群组仅能创建一个邀请链接'}, status=409)

                link = MessageGroupInviteLink.objects.create(
                    group=locked_group,
                    created_by=request.user,
                    expires_at=expires_at,
                    max_uses=max_uses,
                )
                _create_group_audit_log(
                    locked_group,
                    request.user,
                    'invite_link_create',
                    metadata={'invite_id': link.id, 'expires_at': expires_at.isoformat() if expires_at else None, 'max_uses': max_uses},
                )
            return JsonResponse({
                'status': 'success',
                'invite': _invite_link_payload(link, request),
            }, status=201)

        links = group.invite_links.select_related('created_by').order_by('-created_at')[:20]
        return JsonResponse({
            'status': 'success',
            'invites': [_invite_link_payload(link, request) for link in links],
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理群邀请链接错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def group_bans_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupBan, MessageGroupMember
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.method == 'GET':
            bans = (
                MessageGroupBan.objects
                .filter(group=group, revoked_at__isnull=True)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                .select_related('user', 'banned_by')
                .order_by('-created_at')[:100]
            )
            return JsonResponse({'status': 'success', 'bans': [_active_group_ban_payload(ban) for ban in bans]})

        data = json.loads(request.body or '{}')
        try:
            user_id = int(data.get('user_id'))
        except (TypeError, ValueError):
            return JsonResponse({'error': '请选择要封禁的用户'}, status=400)
        if user_id == request.user.id:
            return JsonResponse({'error': '不能封禁自己'}, status=400)

        target_user = get_object_or_404(User, id=user_id, is_active=True)
        target_membership = MessageGroupMember.objects.filter(
            group=group,
            user=target_user,
            left_at__isnull=True,
        ).first()
        if target_membership and not _can_manage_target(membership, target_membership):
            return JsonResponse({'error': '无权封禁该成员'}, status=403)

        reason = _body_string(data, 'reason')[:1000]
        try:
            expires_at = _parse_expires_at(data.get('expires_at'))
        except (TypeError, ValueError):
            return JsonResponse({'error': '过期时间格式错误'}, status=400)
        if expires_at and expires_at <= timezone.now():
            return JsonResponse({'error': '过期时间必须晚于当前时间'}, status=400)

        with transaction.atomic():
            existing = _get_active_group_ban(group, target_user)
            if existing:
                ban = existing
                ban.reason = reason
                ban.expires_at = expires_at
                ban.banned_by = request.user
                ban.save(update_fields=['reason', 'expires_at', 'banned_by'])
            else:
                ban = MessageGroupBan.objects.create(
                    group=group,
                    user=target_user,
                    banned_by=request.user,
                    reason=reason,
                    expires_at=expires_at,
                )
            if target_membership and data.get('remove_member', True):
                target_membership.left_at = timezone.now()
                target_membership.save(update_fields=['left_at'])
            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])
            _create_group_audit_log(
                group,
                request.user,
                'member_ban',
                target_user=target_user,
                metadata={'reason': reason, 'expires_at': expires_at.isoformat() if expires_at else None},
            )

        return JsonResponse({'status': 'success', 'ban': _active_group_ban_payload(ban), 'group': _group_detail_payload(group, membership)}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('处理群封禁错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def revoke_group_ban_api(request, group_id, ban_id):
    try:
        from messaging.models import MessageGroup, MessageGroupBan
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        ban = get_object_or_404(MessageGroupBan.objects.select_related('user'), id=ban_id, group=group)
        if ban.revoked_at is None:
            ban.revoked_at = timezone.now()
            ban.revoked_by = request.user
            ban.save(update_fields=['revoked_at', 'revoked_by'])
            _create_group_audit_log(group, request.user, 'member_unban', target_user=ban.user)
        return JsonResponse({'status': 'success'})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('解除群封禁错误', e)


@require_http_methods(["GET"])
@login_required
def group_audit_logs_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupAuditLog
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error
        try:
            page = max(1, int(request.GET.get('page', '1')))
            page_size = min(100, max(1, int(request.GET.get('page_size', '30'))))
        except ValueError:
            return JsonResponse({'error': '分页参数错误'}, status=400)
        qs = MessageGroupAuditLog.objects.filter(group=group).select_related('actor', 'target_user').order_by('-created_at')
        count = qs.count()
        start = (page - 1) * page_size
        logs = qs[start:start + page_size]
        return JsonResponse({
            'status': 'success',
            'count': count,
            'results': [
                {
                    'id': log.id,
                    'actor': _user_payload(log.actor),
                    'target_user': _user_payload(log.target_user),
                    'action': log.action,
                    'metadata': log.metadata,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取群审计日志错误', e)


@require_http_methods(["GET"])
@login_required
def preview_group_invite_api(request, token):
    try:
        from messaging.models import MessageGroupInviteLink, MessageGroupMember
        link = get_object_or_404(
            MessageGroupInviteLink.objects.select_related('group', 'created_by'),
            token=token,
        )
        group = link.group
        valid = link.is_valid()
        reason = ''
        if link.revoked_at is not None:
            reason = 'revoked'
        elif link.expires_at and link.expires_at <= timezone.now():
            reason = 'expired'
        elif link.max_uses is not None and link.uses_count >= link.max_uses:
            reason = 'max_uses_reached'
        elif not group.is_active:
            reason = 'group_inactive'

        member_limit = _group_member_limit_payload(group)
        membership = MessageGroupMember.objects.filter(group=group, user=request.user, left_at__isnull=True).first()
        ban = _get_active_group_ban(group, request.user)
        if member_limit['is_full'] and not reason:
            reason = 'group_full'
        can_join = bool(valid and membership is None and ban is None and not member_limit['is_full'])
        return JsonResponse({
            'status': 'success',
            'valid': valid,
            'reason': reason,
            'group': {
                'id': group.id,
                'name': group.name,
                'avatar': _group_avatar_url(group),
                'description': group.description,
                'require_approval': group.require_approval,
                **member_limit,
            },
            'link': {
                'expires_at': link.expires_at.isoformat() if link.expires_at else None,
                'max_uses': link.max_uses,
                'uses_count': link.uses_count,
                'remaining_uses': None if link.max_uses is None else max(0, link.max_uses - link.uses_count),
            },
            'viewer': {
                'is_member': membership is not None,
                'is_banned': ban is not None,
                'ban': _active_group_ban_payload(ban),
                'can_join': can_join,
            },
        })
    except Http404:
        return JsonResponse({'error': '邀请链接不存在'}, status=404)
    except Exception as e:
        return _server_error_response('预览群邀请错误', e)


@require_http_methods(["POST", "DELETE"])
@login_required
def revoke_group_invite_link_api(request, group_id, invite_id):
    try:
        from messaging.models import MessageGroup, MessageGroupInviteLink
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        link = get_object_or_404(MessageGroupInviteLink, id=invite_id, group=group)
        if link.revoked_at is None:
            link.revoked_at = timezone.now()
            link.save(update_fields=['revoked_at'])
            _create_group_audit_log(group, request.user, 'invite_link_revoke', metadata={'invite_id': link.id})
        return JsonResponse({'status': 'success', 'invite': _invite_link_payload(link, request)})
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('撤销群邀请链接错误', e)


@require_http_methods(["POST"])
@login_required
def join_group_by_invite_api(request, token):
    try:
        from messaging.models import GroupJoinRequest, MessageGroupInviteLink, MessageGroupInviteUse, MessageGroupMember
        with transaction.atomic():
            link = get_object_or_404(
                MessageGroupInviteLink.objects.select_for_update().select_related('group'),
                token=token,
            )
            locked_group = link.group
            locked_group = locked_group.__class__.objects.select_for_update().get(id=locked_group.id)
            link.group = locked_group
            if not link.is_valid():
                return JsonResponse({'error': '邀请链接已失效'}, status=400)
            active_ban = _get_active_group_ban(link.group, request.user)
            if active_ban:
                return JsonResponse({
                    'error': '你已被该群组封禁，无法通过邀请链接加入',
                    'ban': _active_group_ban_payload(active_ban),
                }, status=403)

            membership = MessageGroupMember.objects.filter(group=link.group, user=request.user).first()
            if membership and membership.left_at is None:
                return JsonResponse({
                    'status': 'success',
                    'already_member': True,
                    'group': _group_detail_payload(link.group, membership),
                })

            current_count = _active_group_member_count(link.group)
            if current_count >= MAX_MESSAGE_GROUP_MEMBERS:
                return _group_full_response(link.group, current_count=current_count)

            if link.group.require_approval:
                request_message = ''
                try:
                    request_message = _body_string(json.loads(request.body or '{}'), 'request_message')[:200]
                except json.JSONDecodeError:
                    request_message = ''
                join_request, created_request = GroupJoinRequest.objects.get_or_create(
                    group=link.group,
                    user=request.user,
                    status='pending',
                    defaults={'request_message': request_message},
                )
                if not created_request and request_message and join_request.request_message != request_message:
                    join_request.request_message = request_message
                    join_request.save(update_fields=['request_message'])
                _create_group_audit_log(
                    link.group,
                    request.user,
                    'join_request_create',
                    target_user=request.user,
                    metadata={'via': 'invite', 'invite_id': link.id, 'request_id': join_request.id},
                )
                return JsonResponse({
                    'status': 'pending',
                    'pending_approval': True,
                    'message': '入群申请已提交，请等待管理员审批',
                    'request_id': join_request.id,
                    'group': {
                        'id': link.group.id,
                        'name': link.group.name,
                        'avatar': _group_avatar_url(link.group),
                    },
                }, status=202)

            if membership is None:
                membership = MessageGroupMember(group=link.group, user=request.user, role='member')
            membership.left_at = None
            membership.role = 'member'
            membership.muted_until = None
            membership.joined_at = timezone.now()
            membership.save()
            link.uses_count += 1
            link.save(update_fields=['uses_count'])
            MessageGroupInviteUse.objects.create(
                invite=link,
                group=link.group,
                user=request.user,
            )
            link.group.updated_at = timezone.now()
            link.group.save(update_fields=['updated_at'])
            _create_group_audit_log(link.group, request.user, 'member_add', target_user=request.user, metadata={'via': 'invite', 'invite_id': link.id})

        return JsonResponse({
            'status': 'success',
            'already_member': False,
            'group': _group_detail_payload(link.group, membership),
        })
    except Http404:
        return JsonResponse({'error': '邀请链接不存在'}, status=404)
    except Exception as e:
        return _server_error_response('加入群组错误', e)
