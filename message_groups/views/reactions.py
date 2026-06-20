from .common import *  # noqa: F401,F403

@require_http_methods(["POST"])
@login_required
def toggle_message_reaction_api(request, group_id, message_id):
    """切换消息表情回应（添加或移除）"""
    try:
        from messaging.models import GroupMessage, GroupMessageReaction, MessageGroup

        data = json.loads(request.body)
        emoji = data.get('emoji', '').strip()

        if not emoji:
            return JsonResponse({'error': '表情符号不能为空'}, status=400)

        if len(emoji) > 20:
            return JsonResponse({'error': '表情符号过长'}, status=400)

        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_member(group, request.user)
        if error is not None:
            return error

        message = get_object_or_404(GroupMessage, id=message_id, group=group, is_recalled=False)

        # 尝试移除已有的反应
        existing = GroupMessageReaction.objects.filter(
            message=message,
            user=request.user,
            emoji=emoji
        ).first()

        if existing:
            existing.delete()
            action = 'removed'
        else:
            # 添加新反应
            GroupMessageReaction.objects.create(
                message=message,
                user=request.user,
                emoji=emoji
            )
            action = 'added'

        # 返回更新后的反应统计
        from django.db.models import Count
        reaction_stats = message.reactions.values('emoji').annotate(count=Count('id'))
        reactions = {}
        for stat in reaction_stats:
            e = stat['emoji']
            count = stat['count']
            users = list(message.reactions.filter(emoji=e).select_related('user')[:3])
            reactions[e] = {
                'count': count,
                'users': [{'user_id': r.user_id, 'username': r.user.username} for r in users],
                'reacted_by_me': any(r.user_id == request.user.id for r in users),
            }

        return JsonResponse({
            'status': 'success',
            'action': action,
            'reactions': reactions,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        return _server_error_response('切换表情回应错误', e)


# ==================== Phase 3: 入群审批 API ====================
