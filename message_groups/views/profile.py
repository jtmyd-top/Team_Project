from .common import *  # noqa: F401,F403

@require_http_methods(["GET", "POST"])
@login_required
def get_group_policy_api(request):
    from messaging.models import MessageGroupPolicy
    policy = MessageGroupPolicy.get_current()

    if request.method == 'POST':
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': '只有管理员可以调整群组创建条件'}, status=403)
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': '请求格式错误'}, status=400)

        try:
            min_public_notes = int(data.get('min_public_notes', policy.min_public_notes))
            min_followers = int(data.get('min_followers', policy.min_followers))
        except (TypeError, ValueError):
            return JsonResponse({'error': '门槛值必须是数字'}, status=400)

        if min_public_notes < 0 or min_followers < 0:
            return JsonResponse({'error': '门槛值不能小于 0'}, status=400)

        policy.enabled = bool(data.get('enabled', policy.enabled))
        policy.min_public_notes = min_public_notes
        policy.min_followers = min_followers
        policy.save(update_fields=['enabled', 'min_public_notes', 'min_followers', 'updated_at'])

    return JsonResponse({'status': 'success', 'policy': _policy_payload(policy, request.user)})


@require_http_methods(["POST"])
@login_required
def create_message_group_api(request):
    try:
        from messaging.models import MessageGroup, MessageGroupMember, MessageGroupPolicy

        data = json.loads(request.body)
        name = _body_string(data, 'name')[:80]
        raw_member_ids = data.get('member_ids') or []
        if not name:
            return JsonResponse({'error': '请输入群组名称'}, status=400)
        if not isinstance(raw_member_ids, list):
            return JsonResponse({'error': 'member_ids 必须是数组'}, status=400)

        policy = MessageGroupPolicy.get_current()
        policy_payload = _policy_payload(policy, request.user)
        if not policy_payload['eligible']:
            return JsonResponse({
                'error': '你暂未满足创建群组条件',
                'policy': policy_payload,
            }, status=403)

        member_ids = []
        for value in raw_member_ids:
            try:
                member_id = int(value)
            except (TypeError, ValueError):
                continue
            if member_id > 0 and member_id != request.user.id and member_id not in member_ids:
                member_ids.append(member_id)
        if not member_ids:
            return JsonResponse({'error': '请至少选择一名群成员'}, status=400)
        if len(member_ids) + 1 > MAX_MESSAGE_GROUP_MEMBERS:
            return JsonResponse({
                'error': f'群聊人数已达上限，最多 {MAX_MESSAGE_GROUP_MEMBERS} 人',
                'member_count': len(member_ids) + 1,
                'max_members': MAX_MESSAGE_GROUP_MEMBERS,
            }, status=400)

        users = list(User.objects.filter(id__in=member_ids, is_active=True))
        if len(users) != len(member_ids):
            return JsonResponse({'error': '部分群成员不存在或不可用'}, status=400)

        with transaction.atomic():
            User.objects.select_for_update().get(id=request.user.id)
            owned_limit = _owned_group_limit_payload(request.user)
            if not owned_limit['within_owned_group_limit']:
                return JsonResponse({
                    'error': f'你已创建 {MAX_OWNED_MESSAGE_GROUPS} 个群聊，暂不能继续创建',
                    'policy': _policy_payload(policy, request.user),
                    **owned_limit,
                }, status=403)

            group = MessageGroup.objects.create(
                name=name,
                owner=request.user,
                created_by=request.user,
            )
            MessageGroupMember.objects.create(group=group, user=request.user, role='owner')
            MessageGroupMember.objects.bulk_create([
                MessageGroupMember(group=group, user=user, role='member')
                for user in users
            ])
            _create_group_audit_log(group, request.user, 'group_create', metadata={'member_count': len(users) + 1})

        return JsonResponse({
            'status': 'success',
            'group': {
                'id': group.id,
                'name': group.name,
                'member_count': len(users) + 1,
                'max_members': MAX_MESSAGE_GROUP_MEMBERS,
                'policy_stats': policy_payload['stats'],
            },
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Exception as e:
        return _server_error_response('创建群组错误', e)


@require_http_methods(["GET", "POST"])
@login_required
def message_group_detail_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        if request.method == "GET":
            return JsonResponse({
                'status': 'success',
                'group': _group_detail_payload(group, membership),
                'settings': _group_settings_payload(membership),
            })

        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        data = json.loads(request.body)
        name = _body_string(data, 'name')[:80]
        if not name:
            return JsonResponse({'error': '请输入群组名称'}, status=400)
        group.name = name
        group.updated_at = timezone.now()
        group.save(update_fields=['name', 'updated_at'])
        _create_group_audit_log(group, request.user, 'group_rename', metadata={'name': name})
        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群组错误', e)


@require_http_methods(["POST", "PATCH"])
@login_required
def update_group_profile_api(request, group_id):
    try:
        from messaging.models import MessageGroup
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error
        manager_error = _require_group_manager(membership)
        if manager_error is not None:
            return manager_error

        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.POST
            avatar = request.FILES.get('avatar')
        else:
            data = json.loads(request.body or '{}')
            avatar = None

        changed_fields = []
        metadata = {}
        if 'name' in data:
            name = _body_string(data, 'name')[:80]
            if not name:
                return JsonResponse({'error': '请输入群组名称'}, status=400)
            if group.name != name:
                metadata['old_name'] = group.name
                metadata['name'] = name
                group.name = name
                changed_fields.append('name')
        if 'description' in data:
            group.description = _body_string(data, 'description')[:1000]
            changed_fields.append('description')
        if 'announcement' in data:
            group.announcement = _body_string(data, 'announcement')[:2000]
            changed_fields.append('announcement')
        if 'require_approval' in data:
            group.require_approval = bool(data.get('require_approval'))
            changed_fields.append('require_approval')
            metadata['require_approval'] = group.require_approval
        if 'members_visible' in data:
            group.members_visible = bool(data.get('members_visible'))
            changed_fields.append('members_visible')
            metadata['members_visible'] = group.members_visible
        if 'allow_member_mention_all' in data:
            group.allow_member_mention_all = bool(data.get('allow_member_mention_all'))
            changed_fields.append('allow_member_mention_all')
            metadata['allow_member_mention_all'] = group.allow_member_mention_all
        if avatar is not None:
            group.avatar = avatar
            changed_fields.append('avatar')

        if changed_fields:
            changed_fields.append('updated_at')
            group.updated_at = timezone.now()
            group.save(update_fields=list(dict.fromkeys(changed_fields)))
            action = 'group_announcement_update' if changed_fields == ['announcement', 'updated_at'] else 'group_update_profile'
            _create_group_audit_log(group, request.user, action, metadata=metadata or {'fields': changed_fields})

        return JsonResponse({'status': 'success', 'group': _group_detail_payload(group, membership)})
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('更新群资料错误', e)
