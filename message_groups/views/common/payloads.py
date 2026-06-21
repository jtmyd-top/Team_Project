"""Group common payloads helpers."""
from .base import *  # noqa: F401,F403
from .announcements import _announcement_history_payload, _latest_active_announcement
from .bans import _is_group_manager, _is_member_muted
from .limits import _owned_group_limit_payload
from .users import _group_avatar_url, _user_payload

def _policy_payload(policy, user, exclude_group_id=None):
    policy_eligible, stats = policy.can_create_group(user)
    owned_limit = _owned_group_limit_payload(user, exclude_group_id=exclude_group_id)
    eligible = policy_eligible and owned_limit['within_owned_group_limit']
    return {
        'enabled': policy.enabled,
        'min_public_notes': policy.min_public_notes,
        'min_followers': policy.min_followers,
        'stats': stats,
        'eligible': eligible,
        'policy_eligible': policy_eligible,
        'owned_group_count': owned_limit['owned_group_count'],
        'max_owned_groups': owned_limit['max_owned_groups'],
        'can_manage': user.is_staff or user.is_superuser,
        'reasons': {
            'public_notes': stats['public_notes'] >= policy.min_public_notes,
            'followers': stats['followers'] >= policy.min_followers,
            'owned_groups': owned_limit['within_owned_group_limit'],
        },
    }

def _pinned_group_message_payload(group, viewer=None):
    message = getattr(group, 'pinned_message', None)
    if not message or getattr(message, 'is_recalled', False):
        return None
    return _group_message_payload(message, viewer=viewer)

def _group_settings_payload(membership):
    return {
        'is_pinned': membership.is_pinned,
        'pinned_at': membership.pinned_at.isoformat() if membership.pinned_at else None,
        'is_muted': membership.is_muted,
        'is_archived': membership.is_archived,
        'disappearing_enabled': False,
        'disappearing_ttl_seconds': 0,
        'force_unread': membership.force_unread,
        'cleared_before': membership.cleared_before.isoformat() if membership.cleared_before else None,
        'group_role': membership.role,
    }

def _group_message_payload(message, viewer=None):
    # Phase 2: 获取回复消息信息
    reply_to_data = None
    if message.reply_to:
        reply_to_data = {
            'id': message.reply_to.id,
            'sender': message.reply_to.sender.username,
            'sender_id': message.reply_to.sender_id,
            'content': message.reply_to.content[:100],  # 只显示前100字符
            'created_at': message.reply_to.created_at.isoformat(),
        }

    # Phase 2: 获取转发消息信息
    forwarded_from_data = None
    if message.forwarded_from:
        forwarded_from_data = {
            'id': message.forwarded_from.id,
            'sender': message.forwarded_from.sender.username,
            'sender_id': message.forwarded_from.sender_id,
            'content': message.forwarded_from.content,
            'created_at': message.forwarded_from.created_at.isoformat(),
            'group_name': message.forwarded_from.group.name if message.forwarded_from.group else None,
        }

    # Phase 2: 获取@提及的用户列表
    mentions = []
    if hasattr(message, 'mentions'):
        mentions = [
            {
                'user_id': mention.mentioned_user_id,
                'username': mention.mentioned_user.username,
            }
            for mention in message.mentions.select_related('mentioned_user').all()
        ]

    # Phase 2: 获取表情回应统计
    reactions = {}
    if hasattr(message, 'reactions'):
        from django.db.models import Count
        reaction_stats = message.reactions.values('emoji').annotate(count=Count('id'))
        for stat in reaction_stats:
            emoji = stat['emoji']
            count = stat['count']
            # 获取使用该表情的用户列表（最多显示3个）
            users = list(message.reactions.filter(emoji=emoji).select_related('user')[:3])
            reactions[emoji] = {
                'count': count,
                'users': [{'user_id': r.user_id, 'username': r.user.username} for r in users],
                'reacted_by_me': viewer and any(r.user_id == viewer.id for r in users) if viewer else False,
            }

    return {
        'id': message.id,
        'conversation_type': 'group',
        'group_id': message.group_id,
        'sender': message.sender.username,
        'sender_id': message.sender_id,
        'sender_avatar': _get_avatar_url(message.sender),
        'recipient': message.group.name,
        'recipient_id': None,
        'content': message.content,
        'content_preview': '',
        'merged_forward': None,
        'created_at': message.created_at.isoformat(),
        'is_edited': message.is_edited,
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'is_read': True,
        'read_at': None,
        'is_own': (viewer is not None and viewer.id == message.sender_id),
        'attachments': [_attachment_payload(a) for a in message.attachments.all()],
        # Phase 2: 新增字段
        'reply_to': reply_to_data,
        'forwarded_from': forwarded_from_data,
        'mentions': mentions,
        'reactions': reactions,
        'is_pinned': bool(
            getattr(message.group, 'pinned_message_id', None) == message.id
        ) if getattr(message, 'group_id', None) else False,
    }

def _member_payload(membership):
    user = membership.user
    muted = _is_member_muted(membership)
    return {
        'user_id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
        'role': membership.role,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        'muted_until': membership.muted_until.isoformat() if membership.muted_until else None,
        'is_group_muted': muted,
        'is_self': False,
    }

def _can_view_group_members(group, viewer_membership):
    if not viewer_membership:
        return False
    return group.members_visible or _is_group_manager(viewer_membership)

def _group_detail_payload(group, viewer_membership=None):
    memberships = list(
        group.memberships
        .filter(left_at__isnull=True)
        .select_related('user')
        .order_by('role', 'joined_at')
    )
    can_view_members = _can_view_group_members(group, viewer_membership)
    visible_memberships = memberships if can_view_members else []
    members = [_member_payload(membership) for membership in visible_memberships]
    if viewer_membership and can_view_members:
        for member in members:
            member['is_self'] = member['user_id'] == viewer_membership.user_id
    current_announcement = _latest_active_announcement(group)
    return {
        'id': group.id,
        'name': group.name,
        'avatar': _group_avatar_url(group),
        'description': group.description,
        'announcement': group.announcement,
        'announcement_pinned_at': group.announcement_pinned_at.isoformat() if group.announcement_pinned_at else None,
        'announcement_message_id': current_announcement.message_id if current_announcement else None,
        'announcement_updated_by': _user_payload(group.announcement_updated_by),
        'announcement_history': [
            _announcement_history_payload(item)
            for item in group.announcement_history
            .filter(deleted_at__isnull=True)
            .select_related('editor', 'message')
            .order_by('-pinned', '-updated_at', '-created_at')[:20]
        ],
        'mute_mode': group.mute_mode,
        'require_approval': group.require_approval,
        'members_visible': group.members_visible,
        'can_view_members': can_view_members,
        'allow_member_mention_all': group.allow_member_mention_all,
        'pinned_message': _pinned_group_message_payload(group, viewer_membership.user if viewer_membership else None),
        'owner_id': group.owner_id,
        'member_count': len(memberships),
        'max_members': MAX_MESSAGE_GROUP_MEMBERS,
        'is_full': len(memberships) >= MAX_MESSAGE_GROUP_MEMBERS,
        'pending_join_request_count': group.join_requests.filter(status='pending').count() if viewer_membership and _is_group_manager(viewer_membership) else 0,
        'created_at': group.created_at.isoformat() if group.created_at else None,
        'updated_at': group.updated_at.isoformat() if group.updated_at else None,
        'viewer_role': viewer_membership.role if viewer_membership else None,
        'members': members,
    }

def _visible_group_messages_qs(group, membership):
    from messaging.models import GroupMessage
    qs = GroupMessage.objects.filter(group=group, is_recalled=False).select_related('sender', 'group').prefetch_related('attachments')
    if membership.cleared_before:
        qs = qs.filter(created_at__gt=membership.cleared_before)
    qs = qs.exclude(deletions__user=membership.user)
    return qs.order_by('created_at')

__all__ = [
    '_policy_payload',
    '_pinned_group_message_payload',
    '_group_settings_payload',
    '_group_message_payload',
    '_member_payload',
    '_can_view_group_members',
    '_group_detail_payload',
    '_visible_group_messages_qs',
]
