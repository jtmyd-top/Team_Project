"""Group common limits helpers."""
from .base import *  # noqa: F401,F403

def _active_owned_group_count(user, exclude_group_id=None):
    from messaging.models import MessageGroup
    qs = MessageGroup.objects.filter(owner=user, is_active=True)
    if exclude_group_id is not None:
        qs = qs.exclude(id=exclude_group_id)
    return qs.count()

def _owned_group_limit_payload(user, exclude_group_id=None):
    owned_count = _active_owned_group_count(user, exclude_group_id=exclude_group_id)
    return {
        'owned_group_count': owned_count,
        'max_owned_groups': MAX_OWNED_MESSAGE_GROUPS,
        'within_owned_group_limit': owned_count < MAX_OWNED_MESSAGE_GROUPS,
    }

def _active_group_member_count(group):
    return group.memberships.filter(left_at__isnull=True).count()

def _group_member_limit_payload(group, current_count=None):
    if current_count is None:
        current_count = _active_group_member_count(group)
    return {
        'member_count': current_count,
        'max_members': MAX_MESSAGE_GROUP_MEMBERS,
        'is_full': current_count >= MAX_MESSAGE_GROUP_MEMBERS,
    }

def _group_full_response(group, current_count=None):
    payload = _group_member_limit_payload(group, current_count=current_count)
    return JsonResponse({
        'error': f'群聊人数已达上限，最多 {MAX_MESSAGE_GROUP_MEMBERS} 人',
        **payload,
    }, status=409)

__all__ = [
    '_active_owned_group_count',
    '_owned_group_limit_payload',
    '_active_group_member_count',
    '_group_member_limit_payload',
    '_group_full_response',
]
