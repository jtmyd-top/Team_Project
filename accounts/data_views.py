"""User-owned data discovery and export endpoints."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods

from message_groups.views.common import _visible_group_messages_qs
from messaging.attachment_access import visible_message_attachments_queryset
from messaging.models import Message, MessageGroupMember
from notes.models import Note


RESULT_LIMIT = 8


def _summary(value, limit=140):
    normalized = " ".join(strip_tags(value or "").split())
    return normalized[:limit] + ("..." if len(normalized) > limit else "")


def _note_payload(note):
    return {
        "id": note.id,
        "type": "note",
        "title": note.title,
        "summary": _summary(note.content),
        "updated_at": note.updated_at.isoformat(),
        "url": f"/knowledge/?note={note.id}",
    }


def _direct_message_payload(message, current_user):
    peer = message.recipient if message.sender_id == current_user.id else message.sender
    return {
        "id": message.id,
        "type": "direct_message",
        "title": peer.username,
        "summary": _summary(message.content),
        "created_at": message.created_at.isoformat(),
        "url": f"/messages/?user_id={peer.id}&message_id={message.id}",
    }


def _group_message_payload(message):
    return {
        "id": message.id,
        "type": "group_message",
        "title": message.group.name,
        "summary": _summary(message.content),
        "created_at": message.created_at.isoformat(),
        "url": f"/messages/?group_id={message.group_id}&message_id={message.id}",
    }


@login_required
@require_http_methods(["GET"])
def global_search_api(request):
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"status": "success", "query": "", "results": {}})
    if len(query) > 80:
        return JsonResponse({"status": "error", "message": "Search query is too long"}, status=400)

    note_filter = Q(title__icontains=query) | Q(content__icontains=query)
    notes = (
        Note.objects.filter(
            Q(author=request.user) | Q(collaborators__user=request.user),
            is_trashed=False,
            is_secret=False,
        )
        .filter(note_filter)
        .distinct()
        .order_by("-updated_at")[:RESULT_LIMIT]
    )

    direct_filter = Q(content__icontains=query) | Q(searchable_text__icontains=query)
    direct_messages = (
        Message.objects.filter(Q(sender=request.user) | Q(recipient=request.user))
        .filter(is_recalled=False)
        .exclude(Q(sender=request.user, deleted_for_sender=True))
        .exclude(Q(recipient=request.user, deleted_for_recipient=True))
        .filter(direct_filter)
        .select_related("sender", "recipient")
        .order_by("-created_at")[:RESULT_LIMIT]
    )

    memberships = list(
        MessageGroupMember.objects.filter(user=request.user, left_at__isnull=True)
        .select_related("group")
        .filter(group__is_active=True)
    )
    groups = [
        {
            "id": membership.group_id,
            "type": "group",
            "title": membership.group.name,
            "summary": _summary(membership.group.description),
            "updated_at": membership.group.updated_at.isoformat(),
            "url": f"/messages/?group_id={membership.group_id}",
        }
        for membership in memberships
        if query.lower() in membership.group.name.lower() or str(membership.group_id) == query
    ][:RESULT_LIMIT]

    group_messages = []
    for membership in memberships:
        matched = (
            _visible_group_messages_qs(membership.group, membership)
            .filter(Q(content__icontains=query) | Q(searchable_text__icontains=query))
            .select_related("group")
            .order_by("-created_at")[:RESULT_LIMIT]
        )
        group_messages.extend(_group_message_payload(item) for item in matched)
    group_messages.sort(key=lambda item: item["created_at"], reverse=True)

    users = (
        User.objects.filter(Q(username__icontains=query) | Q(id__iexact=query))
        .exclude(id=request.user.id)
        .order_by("username")[:RESULT_LIMIT]
    )
    people = [
        {
            "id": user.id,
            "type": "user",
            "title": user.username,
            "summary": "User",
            "url": f"/user/{user.id}/",
        }
        for user in users
    ]

    attachments = (
        visible_message_attachments_queryset(request.user)
        .filter(Q(original_name__icontains=query) | Q(mime_type__icontains=query))
        .order_by("-created_at")[:RESULT_LIMIT]
    )
    files = [
        {
            "id": attachment.id,
            "type": "file",
            "title": attachment.original_name,
            "summary": attachment.mime_type or "Attachment",
            "created_at": attachment.created_at.isoformat(),
            "url": f"/api/messages/attachments/{attachment.id}/file/",
        }
        for attachment in attachments
    ]

    return JsonResponse(
        {
            "status": "success",
            "query": query,
            "results": {
                "notes": [_note_payload(note) for note in notes],
                "messages": [
                    *[_direct_message_payload(message, request.user) for message in direct_messages],
                    *group_messages[:RESULT_LIMIT],
                ],
                "groups": groups,
                "users": people,
                "files": files,
            },
        }
    )


def _attachment_payload(attachment):
    return {
        "id": attachment.id,
        "name": attachment.original_name,
        "type": attachment.attachment_type,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "created_at": attachment.created_at.isoformat(),
    }


@login_required
@require_http_methods(["GET"])
def export_my_data_api(request):
    """Download portable JSON for the user's non-secret notes and visible messages."""

    notes = (
        Note.objects.filter(author=request.user, is_trashed=False, is_secret=False)
        .prefetch_related("tags")
        .order_by("created_at")
    )
    direct_messages = (
        Message.objects.filter(Q(sender=request.user) | Q(recipient=request.user))
        .select_related("sender", "recipient")
        .prefetch_related("attachments")
        .order_by("created_at")
    )
    memberships = list(
        MessageGroupMember.objects.filter(user=request.user, left_at__isnull=True)
        .select_related("group")
        .filter(group__is_active=True)
    )

    exported_groups = []
    for membership in memberships:
        visible_messages = (
            _visible_group_messages_qs(membership.group, membership)
            .select_related("sender")
            .prefetch_related("attachments")
            .order_by("created_at")
        )
        exported_groups.append(
            {
                "id": membership.group_id,
                "name": membership.group.name,
                "role": membership.role,
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "messages": [
                    {
                        "id": message.id,
                        "sender": message.sender.username,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                        "attachments": [_attachment_payload(item) for item in message.attachments.all()],
                    }
                    for message in visible_messages
                ],
            }
        )

    payload = {
        "schema_version": 1,
        "exported_at": timezone.now().isoformat(),
        "user": {"id": request.user.id, "username": request.user.username},
        "notes": [
            {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
                "is_public": note.is_public,
                "tags": [tag.name for tag in note.tags.all()],
            }
            for note in notes
        ],
        "direct_messages": [
            {
                "id": message.id,
                "sender": message.sender.username,
                "recipient": message.recipient.username,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "attachments": [_attachment_payload(item) for item in message.attachments.all()],
            }
            for message in direct_messages
        ],
        "groups": exported_groups,
        "notice": "Secret notes and attachment file binaries are deliberately excluded from this export.",
    }
    response = JsonResponse(payload, json_dumps_params={"ensure_ascii": False, "indent": 2})
    filename = f"knowledge-export-{request.user.id}-{timezone.localdate().isoformat()}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
