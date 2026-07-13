"""Snapshot helpers for note version history."""

from django.db import transaction

from notes.models import Note, NoteRevision


def create_note_revision(note, actor=None, action=NoteRevision.ACTION_UPDATED):
    """Persist the current note state as the next immutable revision."""
    if not note or not note.pk:
        return None

    # A locked note row makes version numbers deterministic during concurrent edits.
    with transaction.atomic():
        locked_note = Note.objects.select_for_update().get(pk=note.pk)
        latest = (
            NoteRevision.objects.filter(note_id=locked_note.id)
            .order_by('-version_number')
            .values_list('version_number', flat=True)
            .first()
        )
        return NoteRevision.objects.create(
            note=locked_note,
            version_number=(latest or 0) + 1,
            title=locked_note.title or '',
            content=locked_note.content or '',
            toc=locked_note.toc or [],
            action=action,
            created_by=actor,
        )
