"""Conversation listing views."""
from .common import *  # noqa: F401, F403


@require_http_methods(["GET"])
@login_required
def get_message_conversations_api(request):
    """Return direct and group conversations for the current user."""
    try:
        from messaging.models import (
            ConversationSettings,
            GroupMessage,
            Message,
            MessageGroupAnnouncementHistory,
            MessageGroupMember,
            UserBlocklist,
        )

        scope = request.GET.get('scope', 'all')

        if scope == 'blocked':
            blocked = UserBlocklist.objects.filter(user=request.user).select_related('blocked_user')
            data = [
                {
                    'user_id': item.blocked_user.id,
                    'username': item.blocked_user.username,
                    'avatar': _get_avatar_url(item.blocked_user),
                    'is_blocked': True,
                    'blocked_at': item.created_at.isoformat() if item.created_at else None,
                    'reason': item.reason,
                }
                for item in blocked
            ]
            return JsonResponse({'status': 'success', 'conversations': data})

        messages = (
            Message.objects.filter(Q(sender=request.user) | Q(recipient=request.user))
            .exclude(is_recalled=True)
            .prefetch_related('attachments')
            .order_by('-created_at')
        )
        messages = messages.exclude(Q(sender=request.user) & Q(deleted_for_sender=True))
        messages = messages.exclude(Q(recipient=request.user) & Q(deleted_for_recipient=True))

        seen_peers = set()
        ordered_peers = []
        for message in messages:
            peer_id = message.recipient_id if message.sender_id == request.user.id else message.sender_id
            if peer_id in seen_peers:
                continue
            seen_peers.add(peer_id)
            ordered_peers.append((peer_id, message))

        peer_ids = [peer_id for peer_id, _ in ordered_peers]
        peer_map = User.objects.filter(id__in=peer_ids).select_related('profile').in_bulk()

        settings_map = {
            item.peer_id: item
            for item in ConversationSettings.objects.filter(user=request.user, peer_id__in=peer_ids)
        }
        missing_settings = [
            ConversationSettings(user=request.user, peer_id=peer_id)
            for peer_id in peer_ids
            if peer_id in peer_map and peer_id not in settings_map
        ]
        if missing_settings:
            ConversationSettings.objects.bulk_create(missing_settings, ignore_conflicts=True)
            settings_map = {
                item.peer_id: item
                for item in ConversationSettings.objects.filter(user=request.user, peer_id__in=peer_ids)
            }

        peer_settings_map = {
            item.user_id: item
            for item in ConversationSettings.objects.filter(user_id__in=peer_ids, peer=request.user)
        }
        blocked_ids = set(
            UserBlocklist.objects.filter(user=request.user).values_list('blocked_user_id', flat=True)
        )

        unread_filter = Q()
        for peer_id in peer_ids:
            settings_obj = settings_map.get(peer_id)
            peer_filter = Q(sender_id=peer_id)
            if settings_obj and settings_obj.cleared_before:
                peer_filter &= Q(created_at__gt=settings_obj.cleared_before)
            unread_filter |= peer_filter

        if unread_filter:
            unread_map = {
                row['sender_id']: row['total']
                for row in (
                    Message.objects.filter(
                        unread_filter,
                        recipient=request.user,
                        is_read=False,
                        is_recalled=False,
                        deleted_for_recipient=False,
                    )
                    .values('sender_id')
                    .annotate(total=Count('id'))
                )
            }
        else:
            unread_map = {}

        conversations = []
        for peer_id, last_message in ordered_peers:
            peer = peer_map.get(peer_id)
            if peer is None:
                continue

            settings_obj = settings_map[peer_id]
            peer_settings = peer_settings_map.get(peer_id)

            if settings_obj.disappearing_enabled or (peer_settings and peer_settings.disappearing_enabled):
                _apply_disappearing(request.user, peer, settings_obj, peer_settings)

            if scope == 'archived' and not settings_obj.is_archived:
                continue
            if scope in ('all', 'unread') and settings_obj.is_archived:
                continue
            if peer_id in blocked_ids and scope != 'blocked':
                continue
            if settings_obj.cleared_before and last_message.created_at <= settings_obj.cleared_before:
                continue

            unread_count = unread_map.get(peer_id, 0)
            if unread_count == 0 and settings_obj.force_unread:
                unread_count = 1
            if scope == 'unread' and unread_count == 0:
                continue

            conversations.append({
                'conversation_type': 'user',
                'user_id': peer.id,
                'username': peer.username,
                'avatar': _get_avatar_url(peer),
                'last_message': _message_preview(last_message),
                'last_message_time': last_message.created_at.isoformat(),
                'last_sender_id': last_message.sender_id,
                'unread_count': unread_count,
                'is_pinned': settings_obj.is_pinned,
                'pinned_at': settings_obj.pinned_at.isoformat() if settings_obj.pinned_at else None,
                'is_muted': settings_obj.is_muted,
                'is_archived': settings_obj.is_archived,
                'disappearing_enabled': settings_obj.disappearing_enabled,
                'force_unread': settings_obj.force_unread,
                'is_blocked': peer_id in blocked_ids,
            })

        memberships = list(
            MessageGroupMember.objects.filter(
                user=request.user,
                left_at__isnull=True,
                group__is_active=True,
            ).select_related('group')
        )
        scoped_memberships = []
        for membership in memberships:
            if scope == 'archived' and not membership.is_archived:
                continue
            if scope in ('all', 'unread') and membership.is_archived:
                continue
            scoped_memberships.append(membership)

        announcement_map = {}
        last_group_message_map = {}
        group_unread_map = {}
        group_ids = [membership.group_id for membership in scoped_memberships]

        if group_ids:
            announcements = (
                MessageGroupAnnouncementHistory.objects.filter(
                    group_id__in=group_ids,
                    deleted_at__isnull=True,
                )
                .select_related('message')
                .order_by('group_id', '-pinned', '-updated_at', '-created_at')
            )
            for announcement in announcements:
                announcement_map.setdefault(announcement.group_id, announcement)

            visible_filters = []
            unread_filters = []
            for membership in scoped_memberships:
                visible_filter = Q(group_id=membership.group_id, is_recalled=False)
                if membership.cleared_before:
                    visible_filter &= Q(created_at__gt=membership.cleared_before)
                visible_filters.append(visible_filter)

                threshold = membership.last_read_at
                if membership.cleared_before and (
                    threshold is None or membership.cleared_before > threshold
                ):
                    threshold = membership.cleared_before

                unread_filter = Q(group_id=membership.group_id)
                if threshold:
                    unread_filter &= Q(created_at__gt=threshold)
                unread_filters.append(unread_filter)

            visible_message_filter = visible_filters[0]
            for extra_filter in visible_filters[1:]:
                visible_message_filter |= extra_filter

            group_messages = (
                GroupMessage.objects.filter(visible_message_filter)
                .exclude(deletions__user=request.user)
                .select_related('sender')
                .order_by('group_id', '-created_at')
            )
            for group_message in group_messages:
                last_group_message_map.setdefault(group_message.group_id, group_message)

            unread_filter = unread_filters[0]
            for extra_filter in unread_filters[1:]:
                unread_filter |= extra_filter

            group_unread_map = {
                row['group_id']: row['total']
                for row in (
                    GroupMessage.objects.filter(unread_filter, is_recalled=False)
                    .exclude(sender=request.user)
                    .exclude(deletions__user=request.user)
                    .values('group_id')
                    .annotate(total=Count('id'))
                )
            }

        for membership in scoped_memberships:
            group = membership.group
            announcement = announcement_map.get(group.id)
            last_group_message = last_group_message_map.get(group.id)
            unread_count = group_unread_map.get(group.id, 0)

            if unread_count == 0 and membership.force_unread:
                unread_count = 1
            if scope == 'unread' and unread_count == 0:
                continue

            conversations.append({
                'conversation_type': 'group',
                'group_id': group.id,
                'user_id': None,
                'username': group.name,
                'avatar': (
                    group.avatar.url
                    if getattr(group, 'avatar', None)
                    else '/static/img/default-avatar.png'
                ),
                'last_message': last_group_message.content if last_group_message else '群组已创建',
                'last_message_time': (
                    last_group_message.created_at if last_group_message else group.updated_at
                ).isoformat(),
                'last_sender_id': last_group_message.sender_id if last_group_message else None,
                'unread_count': unread_count,
                'is_pinned': membership.is_pinned,
                'pinned_at': membership.pinned_at.isoformat() if membership.pinned_at else None,
                'is_muted': membership.is_muted,
                'is_archived': membership.is_archived,
                'disappearing_enabled': False,
                'force_unread': membership.force_unread,
                'is_blocked': False,
                'viewer_role': membership.role,
                'announcement': announcement.content if announcement else '',
                'announcement_pinned': bool(announcement and announcement.pinned),
                'announcement_message_id': announcement.message_id if announcement else None,
                'announcement_updated_at': (
                    announcement.updated_at.isoformat()
                    if announcement and announcement.updated_at
                    else None
                ),
            })

        conversations.sort(
            key=lambda conversation: (
                not conversation['is_pinned'],
                -(
                    datetime.fromisoformat(conversation['pinned_at']).timestamp()
                    if conversation.get('pinned_at')
                    else 0
                ),
                -datetime.fromisoformat(conversation['last_message_time']).timestamp(),
            )
        )
        return JsonResponse({'status': 'success', 'conversations': conversations})
    except Http404:
        raise
    except Exception as exc:
        return _server_error_response('获取会话列表失败', exc)
