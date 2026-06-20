"""Group common bans helpers."""
from .base import *  # noqa: F401,F403
from .users import _user_payload

def _get_active_group_ban(group, user):
    from messaging.models import MessageGroupBan
    now = timezone.now()
    return (
        MessageGroupBan.objects
        .filter(group=group, user=user, revoked_at__isnull=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related('banned_by')
        .first()
    )

def _active_group_ban_payload(ban):
    if ban is None:
        return None
    return {
        'id': ban.id,
        'user': _user_payload(ban.user),
        'reason': ban.reason,
        'expires_at': ban.expires_at.isoformat() if ban.expires_at else None,
        'created_at': ban.created_at.isoformat() if ban.created_at else None,
        'banned_by': _user_payload(ban.banned_by),
    }

def _can_send_group_message(group, membership):
    if _is_member_muted(membership):
        return JsonResponse({
            'error': '你已被群内禁言',
            'muted_until': membership.muted_until.isoformat() if membership.muted_until else None,
        }, status=403)
    if _get_active_group_ban(group, membership.user):
        return JsonResponse({'error': '你已被该群组封禁，无法发言'}, status=403)
    if getattr(group, 'mute_mode', 'none') == 'admins_only' and membership.role not in ('owner', 'admin'):
        return JsonResponse({'error': '当前群已开启全员禁言，仅群主或管理员可以发言'}, status=403)
    return None

def _get_active_membership(group, user):
    from messaging.models import MessageGroupMember
    return MessageGroupMember.objects.filter(group=group, user=user, left_at__isnull=True).first()

def _require_group_member(group, user):
    membership = _get_active_membership(group, user)
    if membership is None:
        return None, JsonResponse({'error': '你不是该群组成员'}, status=403)
    return membership, None

def _is_group_manager(membership):
    return membership is not None and membership.role in ('owner', 'admin')

def _require_group_manager(membership):
    if not _is_group_manager(membership):
        return JsonResponse({'error': '只有群主或管理员可以执行该操作'}, status=403)
    return None

def _require_group_owner(membership):
    if membership is None or membership.role != 'owner':
        return JsonResponse({'error': '只有群主可以执行该操作'}, status=403)
    return None

def _can_manage_target(actor_membership, target_membership):
    if actor_membership is None or target_membership is None:
        return False
    if target_membership.role == 'owner':
        return False
    if actor_membership.role == 'owner':
        return actor_membership.user_id != target_membership.user_id
    if actor_membership.role == 'admin':
        return target_membership.role == 'member'
    return False

def _parse_mute_until(data):
    value = data.get('duration') if isinstance(data, dict) else None
    if value in ('none', 'off', 'unmute', False):
        return None
    if value in ('forever', 'permanent', 0, '0'):
        return timezone.now() + timedelta(days=3650)

    minutes = data.get('duration_minutes') if isinstance(data, dict) else None
    if minutes is None:
        minutes = value
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(1, min(minutes, 60 * 24 * 30))
    return timezone.now() + timedelta(minutes=minutes)

def _is_member_muted(membership):
    if not membership or not membership.muted_until:
        return False
    now = timezone.now()
    if membership.muted_until <= now:
        membership.muted_until = None
        membership.save(update_fields=['muted_until'])
        return False
    return True

__all__ = [
    '_get_active_group_ban',
    '_active_group_ban_payload',
    '_can_send_group_message',
    '_get_active_membership',
    '_require_group_member',
    '_is_group_manager',
    '_require_group_manager',
    '_require_group_owner',
    '_can_manage_target',
    '_parse_mute_until',
    '_is_member_muted',
]
