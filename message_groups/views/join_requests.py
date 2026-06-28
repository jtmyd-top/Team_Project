from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def request_join_group_api(request, group_id):
    """申请加入群组（需要审批时使用）"""
    try:
        from messaging.models import GroupJoinRequest, MessageGroup

        data = json.loads(request.body)
        request_message = data.get('message', '').strip()

        if len(request_message) > 200:
            return JsonResponse({'error': '申请留言不能超过200字'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)

        # 检查是否需要审批
        if not group.require_approval:
            return JsonResponse({'error': '此群组无需审批，请直接通过邀请链接加入'}, status=400)

        # 检查是否已经是成员
        from messaging.models import MessageGroupMember
        existing_membership = MessageGroupMember.objects.filter(
            group=group,
            user=request.user,
            left_at__isnull=True
        ).first()

        if existing_membership:
            return JsonResponse({'error': '你已经是群成员'}, status=400)

        member_limit = _group_member_limit_payload(group)
        if member_limit['is_full']:
            return _group_full_response(group, current_count=member_limit['member_count'])

        # 检查是否有待处理的申请
        pending_request = GroupJoinRequest.objects.filter(
            group=group,
            user=request.user,
            status='pending'
        ).first()

        if pending_request:
            return JsonResponse({'error': '你已有待处理的入群申请'}, status=400)

        # 创建申请
        join_request = GroupJoinRequest.objects.create(
            group=group,
            user=request.user,
            request_message=request_message,
            status='pending'
        )

        # 通知群主和管理员
        admins = MessageGroupMember.objects.filter(
            group=group,
            role__in=['owner', 'admin'],
            left_at__isnull=True
        ).select_related('user')

        # 实时推送通知
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()

        for admin_member in admins:
            try:
                notify_user(
                    admin_member.user,
                    'group_join_request',
                    f'{request.user.username} 申请加入群组',
                    f'群组：{group.name}\n留言：{request_message}',
                    group_id=group.id,
                    request_id=join_request.id,
                )

                # 实时 WebSocket 推送
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f'chat_user_{admin_member.user.id}',
                        {
                            'type': 'group_join_request',
                            'group_id': group.id,
                            'group_name': group.name,
                            'request_id': join_request.id,
                            'user': {
                                'id': request.user.id,
                                'username': request.user.username,
                                'avatar': _get_avatar_url(request.user),
                            },
                            'request_message': request_message,
                        }
                    )
            except Exception as e:
                logger.warning(f'发送入群申请通知失败: {e}')

        return JsonResponse({
            'status': 'success',
            'message': '申请已提交，请等待管理员审批',
            'request_id': join_request.id,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('申请加入群组错误', e)


@require_http_methods(["GET"])
@login_required
def all_pending_join_requests_api(request):
    """获取用户管理的所有群组的待审核申请（用于消息列表待审核标签）"""
    try:
        from messaging.models import GroupJoinRequest, MessageGroup, MessageGroupMember

        # 获取用户作为管理员或群主的所有群组
        managed_groups = MessageGroup.objects.filter(
            memberships__user=request.user,
            memberships__role__in=['owner', 'admin'],
            memberships__left_at__isnull=True,
            is_active=True
        ).distinct()

        # 获取这些群组的所有待审核申请
        requests_qs = GroupJoinRequest.objects.filter(
            group__in=managed_groups,
            status='pending'
        ).select_related('user', 'group').order_by('-created_at')

        # 限制返回数量，避免数据过多
        requests_qs = requests_qs[:100]

        results = []
        for req in requests_qs:
            results.append({
                'id': req.id,
                'user': {
                    'id': req.user.id,
                    'username': req.user.username,
                    'avatar': _get_avatar_url(req.user),
                },
                'group': {
                    'id': req.group.id,
                    'name': req.group.name,
                    'avatar': _group_avatar_url(req.group),
                },
                'request_message': req.request_message,
                'created_at': req.created_at.isoformat(),
            })

        return JsonResponse({
            'status': 'success',
            'requests': results,
            'count': len(results),
            'managed_group_count': managed_groups.count(),
        })
    except Exception as e:
        return _server_error_response('获取待审核申请列表错误', e)


@require_http_methods(["GET"])
@login_required
def group_join_requests_api(request, group_id):
    """获取群组的入群申请列表（群主和管理员可查看）"""
    try:
        from messaging.models import GroupJoinRequest, MessageGroup

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以查看
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        status_filter = request.GET.get('status', 'pending')
        requests = GroupJoinRequest.objects.filter(
            group=group,
            status=status_filter
        ).select_related('user', 'reviewed_by').order_by('-created_at')

        results = []
        for req in requests:
            results.append({
                'id': req.id,
                'user': {
                    'id': req.user.id,
                    'username': req.user.username,
                    'avatar': _get_avatar_url(req.user),
                },
                'request_message': req.request_message,
                'status': req.status,
                'reviewed_by': {
                    'id': req.reviewed_by.id,
                    'username': req.reviewed_by.username,
                } if req.reviewed_by else None,
                'rejection_reason': req.rejection_reason,
                'created_at': req.created_at.isoformat(),
                'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
            })

        return JsonResponse({
            'status': 'success',
            'requests': results,
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('获取入群申请列表错误', e)


@require_http_methods(["POST"])
@login_required
def review_join_request_api(request, group_id, request_id):
    """审批入群申请"""
    try:
        from messaging.models import GroupJoinRequest, MessageGroup, MessageGroupAuditLog, MessageGroupMember

        data = json.loads(request.body)
        action = data.get('action')  # 'approve' 或 'reject'
        rejection_reason = data.get('rejection_reason', '').strip()

        if action not in ['approve', 'reject']:
            return JsonResponse({'error': '无效的审批操作'}, status=400)

        if action == 'reject' and not rejection_reason:
            return JsonResponse({'error': '拒绝申请需要填写原因'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主和管理员可以审批
        if membership.role not in ['owner', 'admin']:
            return JsonResponse({'error': '权限不足'}, status=403)

        join_request = get_object_or_404(GroupJoinRequest, id=request_id, group=group)

        if join_request.status != 'pending':
            return JsonResponse({'error': '该申请已被处理'}, status=400)

        with transaction.atomic():
            if action == 'approve':
                locked_group = MessageGroup.objects.select_for_update().get(id=group.id)
                current_count = _active_group_member_count(locked_group)
                existing_active = MessageGroupMember.objects.filter(
                    group=locked_group,
                    user=join_request.user,
                    left_at__isnull=True,
                ).exists()
                if not existing_active and current_count >= MAX_MESSAGE_GROUP_MEMBERS:
                    return _group_full_response(locked_group, current_count=current_count)

                target_member, created_member = MessageGroupMember.objects.get_or_create(
                    group=locked_group,
                    user=join_request.user,
                    defaults={'role': 'member'},
                )
                if not created_member:
                    now = timezone.now()
                    target_member.left_at = None
                    target_member.role = 'member'
                    target_member.muted_until = None
                    target_member.joined_at = now
                    target_member.cleared_before = None if locked_group.allow_new_members_view_history else now
                    target_member.save(update_fields=['left_at', 'role', 'muted_until', 'joined_at', 'cleared_before'])
                join_request.status = 'approved'
                join_request.reviewed_by = request.user
                join_request.reviewed_at = timezone.now()
                join_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

                # 记录审计日志
                MessageGroupAuditLog.objects.create(
                    group=locked_group,
                    actor=request.user,
                    target_user=join_request.user,
                    action='member_add',
                    metadata={'via': 'join_request_approval', 'request_id': request_id}
                )

                # 通知申请人
                notify_user(
                    join_request.user,
                    'group_join_approved',
                    '入群申请已通过',
                    f'你的加入 {group.name} 的申请已通过',
                    group_id=locked_group.id,
                )

                message = '申请已通过'
            else:
                # 拒绝申请
                join_request.status = 'rejected'
                join_request.reviewed_by = request.user
                join_request.reviewed_at = timezone.now()
                join_request.rejection_reason = rejection_reason
                join_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])

                # 通知申请人
                notify_user(
                    join_request.user,
                    'group_join_rejected',
                    '入群申请被拒绝',
                    f'你的加入 {group.name} 的申请被拒绝\n原因：{rejection_reason}',
                    group_id=group.id,
                )

                message = '申请已拒绝'

            group.updated_at = timezone.now()
            group.save(update_fields=['updated_at'])

        return JsonResponse({
            'status': 'success',
            'message': message,
            'group': _group_detail_payload(group, membership),
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('审批入群申请错误', e)


# ==================== Phase 3: 群公告管理 API ====================
