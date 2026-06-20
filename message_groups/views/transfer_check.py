from .common import *  # noqa: F401,F403

@require_http_methods(["GET"])
@login_required
def check_transfer_eligibility_api(request, group_id, user_id):
    """检查指定用户是否满足群主转让条件"""
    try:
        from messaging.models import MessageGroup, MessageGroupMember, MessageGroupPolicy

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        # 只有群主可以查询转让资格
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        # 验证目标用户是群成员
        target_membership = get_object_or_404(
            MessageGroupMember,
            group=group,
            user_id=user_id,
            left_at__isnull=True,
        )

        # 获取群组创建策略
        policy = MessageGroupPolicy.get_current()
        policy_eligible, stats = policy.can_create_group(target_membership.user)
        owned_limit = _owned_group_limit_payload(target_membership.user, exclude_group_id=group.id)
        eligible = policy_eligible and owned_limit['within_owned_group_limit']

        return JsonResponse({
            'status': 'success',
            'eligible': eligible,
            'policy_eligible': policy_eligible,
            'stats': stats,
            'policy': {
                'enabled': policy.enabled,
                'min_public_notes': policy.min_public_notes,
                'min_followers': policy.min_followers,
            },
            'owned_group_count': owned_limit['owned_group_count'],
            'max_owned_groups': owned_limit['max_owned_groups'],
            'reasons': {
                'public_notes': stats['public_notes'] >= policy.min_public_notes,
                'followers': stats['followers'] >= policy.min_followers,
                'owned_groups': owned_limit['within_owned_group_limit'],
            },
            'user': {
                'id': target_membership.user.id,
                'username': target_membership.user.username,
            },
        })
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('检查转让资格错误', e)


# ==================== Phase 2: 表情回应 API ====================
