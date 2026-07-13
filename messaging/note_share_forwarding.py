"""Helpers for preserving note cards when messages are forwarded."""

from django.core.exceptions import ObjectDoesNotExist


class NoteShareForwardingError(ValueError):
    """Raised when a note card can no longer be forwarded."""


def get_note_share(message):
    """Return a direct or group note share attached to a message, if present."""
    try:
        return message.note_share
    except ObjectDoesNotExist:
        return None


def ensure_note_share_is_forwardable(share):
    if share is None:
        return
    if share.revoked_at is not None:
        raise NoteShareForwardingError('该笔记分享已被撤销，无法转发')
    if share.note.is_trashed or share.note.is_secret:
        raise NoteShareForwardingError('该笔记已不可用，无法转发')
    if not share.allow_forwarding:
        raise NoteShareForwardingError('该笔记分享已禁止转发')


def create_direct_note_share_from_forward(source_share, message, shared_by, recipient):
    """Attach a fresh direct share record to a forwarded note-card message."""
    if source_share is None:
        return None

    from messaging.models import DirectNoteShare

    return DirectNoteShare.objects.create(
        message=message,
        note=source_share.note,
        shared_by=shared_by,
        recipient=recipient,
        title_snapshot=source_share.title_snapshot or source_share.note.title,
        was_public_at_share=source_share.was_public_at_share,
        allow_forwarding=source_share.allow_forwarding,
    )


def create_group_note_share_from_forward(source_share, message, shared_by, group):
    """Attach a fresh group share record to a forwarded note-card message."""
    if source_share is None:
        return None

    from messaging.models import GroupNoteShare

    return GroupNoteShare.objects.create(
        group=group,
        message=message,
        note=source_share.note,
        shared_by=shared_by,
        title_snapshot=source_share.title_snapshot or source_share.note.title,
        was_public_at_share=source_share.was_public_at_share,
        allow_forwarding=source_share.allow_forwarding,
    )
