from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def transfer_group_ownership_api(request, group_id):
    try:
        from messaging.models import MessageGroup, MessageGroupMember, MessageGroupPolicy
        data = json.loads(request.body or '{}')
        # 支持 user_id 和 new_owner_id 两种参数名
        target_user_id = int(data.get('new_owner_id') or data.get('user_id'))
        password = data.get('password', '')

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        owner_error = _require_group_owner(membership)
        if owner_error is not None:
            return owner_error

        # 验证密码（可选，增强安全性）
        if password and not request.user.check_password(password):
            return JsonResponse({'error': '密码验证失败'}, status=403)

        with transaction.atomic():
            current_owner = MessageGroupMember.objects.select_for_update().get(
                group=group, user=request.user, left_at__isnull=True
            )
            target = get_object_or_404(
                MessageGroupMember.objects.select_for_update().select_related('user'),
                group=group,
                user_id=target_user_id,
                left_at__isnull=True,
            )
            if target.user_id == request.user.id:
                return JsonResponse({'error': '不能转让给自己'}, status=400)
            User.objects.select_for_update().get(id=target.user_id)

            # 【新增】验证新群主是否满足开群条件
            policy = MessageGroupPolicy.get_current()
            eligible, stats = policy.can_create_group(target.user)

            if not eligible:
                return JsonResponse({
                    'error': '新群主不满足创建群组条件',
                    'policy': _policy_payload(policy, target.user),
                    'stats': stats,
                    'message': f'新群主需同时满足：公开文章数 ≥ {policy.min_public_notes} 且 关注者数 ≥ {policy.min_followers}。'
                               f'当前状态：公开文章 {stats["public_notes"]} 篇，关注者 {stats["followers"]} 人。',
                }, status=403)
            owned_limit = _owned_group_limit_payload(target.user, exclude_group_id=group.id)
            if not owned_limit['within_owned_group_limit']:
                return JsonResponse({
                    'error': f'新群主已拥有 {MAX_OWNED_MESSAGE_GROUPS} 个群聊，无法继续接收转让',
                    **owned_limit,
                }, status=403)

            current_owner.role = 'admin'
            target.role = 'owner'
            current_owner.save(update_fields=['role'])
            target.save(update_fields=['role'])
            group.owner = target.user
            group.updated_at = timezone.now()
            group.save(update_fields=['owner', 'updated_at'])
            _create_group_audit_log(
                group,
                request.user,
                'ownership_transfer',
                target_user=target.user,
                metadata={'old_owner_id': request.user.id, 'new_owner_id': target.user_id},
            )
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, target)})
    except (TypeError, ValueError):
        return JsonResponse({'error': '请选择新的群主'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('转让群主错误', e)
