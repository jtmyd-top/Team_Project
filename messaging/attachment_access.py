"""Shared visibility rules for message attachments."""

from django.db.models import Q


def visible_message_attachments_queryset(user, *, scope="accessible"):
    """
    Return attachments the user can currently access.

    ``scope=mine`` preserves the original asset-center behavior.  The
    accessible scope includes only drafts owned by the user and attachments
    attached to messages that remain visible to them.
    """
    from message_groups.views.common import _visible_group_messages_qs
    from messaging.models import MessageAttachment, MessageGroupMember

    queryset = MessageAttachment.objects.all()
    if scope == "mine":
        return queryset.filter(uploader=user)

    direct_visibility = (
        Q(
            message__sender=user,
            message__is_recalled=False,
            message__deleted_for_sender=False,
        )
        | Q(
            message__recipient=user,
            message__is_recalled=False,
            message__deleted_for_recipient=False,
        )
    )
    group_visibility = Q()
    memberships = (
        MessageGroupMember.objects.filter(user=user, left_at__isnull=True)
        .select_related("group")
        .filter(group__is_active=True)
    )
    for membership in memberships:
        group_visibility |= Q(
            group_message__in=_visible_group_messages_qs(membership.group, membership)
        )

    return queryset.filter(
        Q(uploader=user, message__isnull=True, group_message__isnull=True)
        | direct_visibility
        | group_visibility
    ).distinct()
