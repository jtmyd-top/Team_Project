"""Saved-message endpoints for direct and group conversations."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods

from messaging.models import Message, MessageGroup, MessageGroupMember, SavedMessage


BOOKMARK_LIMIT = 100


def _summary(content, limit=180):
    text = ' '.join(strip_tags(content or '').split())
    return text[:limit] + ('...' if len(text) > limit else '')


def _avatar_url(user):
    profile = getattr(user, 'profile', None)
    avatar = getattr(profile, 'avatar', None)
    return avatar.url if avatar else ''


def _request_data(request):
    try:
        return json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return None


def _visible_group_messages(group, membership):
    # Import lazily because message-group helpers import messaging view constants.
    from message_groups.views.common import _visible_group_messages_qs
    return _visible_group_messages_qs(group, membership)


def _require_group_membership(group, user):
    from message_groups.views.common import _require_group_member
    return _require_group_member(group, user)


def _direct_bookmark_payload(bookmark, viewer):
    message = bookmark.direct_message
    peer = message.recipient if message.sender_id == viewer.id else message.sender
    return {
        'id': bookmark.id,
        'message_id': message.id,
        'conversation_type': 'direct',
        'peer_id': peer.id,
        'title': peer.username,
        'avatar': _avatar_url(peer),
        'content': _summary(message.content),
        'created_at': message.created_at.isoformat(),
        'saved_at': bookmark.created_at.isoformat(),
    }


def _group_bookmark_payload(bookmark):
    message = bookmark.group_message
    group = message.group
    return {
        'id': bookmark.id,
        'message_id': message.id,
        'conversation_type': 'group',
        'group_id': group.id,
        'title': group.name,
        'avatar': getattr(group.avatar, 'url', '') if group.avatar else '',
        'sender': message.sender.username,
        'content': _summary(message.content),
        'created_at': message.created_at.isoformat(),
        'saved_at': bookmark.created_at.isoformat(),
    }


@login_required
@require_http_methods(['GET'])
def list_saved_messages_api(request):
    bookmarks = list(
        SavedMessage.objects.filter(user=request.user)
        .select_related(
            'direct_message__sender',
            'direct_message__recipient',
            'group_message__sender',
            'group_message__group',
        )
        .order_by('-created_at')[:BOOKMARK_LIMIT]
    )
    group_ids = {
        item.group_message.group_id
        for item in bookmarks
        if item.group_message_id and item.group_message.group.is_active
    }
    memberships = {
        item.group_id: item
        for item in MessageGroupMember.objects.filter(
            user=request.user,
            group_id__in=group_ids,
            left_at__isnull=True,
        ).select_related('group')
    }

    items = []
    for bookmark in bookmarks:
        if bookmark.direct_message_id:
            if bookmark.direct_message.visible_to(request.user):
                items.append(_direct_bookmark_payload(bookmark, request.user))
            continue
        if not bookmark.group_message_id:
            continue
        membership = memberships.get(bookmark.group_message.group_id)
        if membership is None:
            continue
        visible = _visible_group_messages(membership.group, membership).filter(
            id=bookmark.group_message_id
        ).exists()
        if visible:
            items.append(_group_bookmark_payload(bookmark))

    return JsonResponse({'status': 'success', 'items': items})


@login_required
@require_http_methods(['POST'])
def toggle_saved_message_api(request):
    data = _request_data(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    try:
        message_id = int(data.get('message_id'))
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid message'}, status=400)
    if message_id <= 0:
        return JsonResponse({'status': 'error', 'message': 'Invalid message'}, status=400)

    conversation_type = str(data.get('conversation_type') or '').strip().lower()
    if conversation_type == 'direct':
        message = get_object_or_404(
            Message.objects.select_related('sender', 'recipient'),
            id=message_id,
        )
        if request.user.id not in (message.sender_id, message.recipient_id) or not message.visible_to(request.user):
            return JsonResponse({'status': 'error', 'message': 'Message is unavailable'}, status=404)
        bookmark, created = SavedMessage.objects.get_or_create(
            user=request.user,
            direct_message=message,
        )
    elif conversation_type == 'group':
        try:
            group_id = int(data.get('group_id'))
        except (TypeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Invalid group'}, status=400)
        group = get_object_or_404(MessageGroup, id=group_id, is_active=True)
        membership, error = _require_group_membership(group, request.user)
        if error is not None:
            return error
        message = get_object_or_404(
            _visible_group_messages(group, membership).select_related('sender', 'group'),
            id=message_id,
        )
        bookmark, created = SavedMessage.objects.get_or_create(
            user=request.user,
            group_message=message,
        )
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid conversation type'}, status=400)

    if created:
        return JsonResponse({'status': 'success', 'saved': True, 'bookmark_id': bookmark.id}, status=201)
    bookmark.delete()
    return JsonResponse({'status': 'success', 'saved': False})
