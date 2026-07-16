"""Version history APIs for collaboratively managed notes."""

import difflib

from bs4 import BeautifulSoup
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .common import login_required, notify_user
from notes.models import Note, NoteRevision
from notes.revisions import create_note_revision


def _revision_payload(revision, include_content=False):
    payload = {
        'id': revision.id,
        'version_number': revision.version_number,
        'action': revision.action,
        'created_at': timezone.localtime(revision.created_at).strftime('%Y-%m-%d %H:%M'),
        'created_by': {
            'id': revision.created_by_id,
            'username': revision.created_by.username if revision.created_by else '系统',
        },
    }
    if include_content:
        payload.update({
            'title': revision.title,
            'content': revision.content,
            'toc': revision.toc or [],
        })
    return payload


def _history_permission(note, user):
    return note.has_write_permission(user) and not note.is_trashed


@login_required
@require_http_methods(['GET'])
def note_revisions_api(request, note_id):
    revision_qs = NoteRevision.objects.select_related('created_by', 'note').filter(note_id=note_id)
    note = get_object_or_404(Note, id=note_id)
    if not _history_permission(note, request.user):
        return JsonResponse({'error': '无权查看此笔记的版本历史'}, status=403)

    # Existing notes predate the feature. Create their baseline lazily instead
    # of shipping a long-running data migration against production content.
    if not revision_qs.exists():
        create_note_revision(note, note.last_modified_by or note.author, action=NoteRevision.ACTION_CREATED)
    revisions = revision_qs.order_by('-version_number')[:100]
    return JsonResponse({
        'note_id': note.id,
        'revisions': [_revision_payload(item) for item in revisions],
        'can_restore': note.has_manage_permission(request.user),
    })


@login_required
@require_http_methods(['GET'])
def note_revision_detail_api(request, note_id, revision_id):
    revision = get_object_or_404(
        NoteRevision.objects.select_related('note', 'created_by'),
        id=revision_id,
        note_id=note_id,
    )
    if not _history_permission(revision.note, request.user):
        return JsonResponse({'error': '无权查看此笔记的版本历史'}, status=403)
    return JsonResponse({'revision': _revision_payload(revision, include_content=True)})


@login_required
@require_http_methods(['GET'])
def note_revision_compare_api(request, note_id):
    try:
        from_id = int(request.GET.get('from', ''))
        to_id = int(request.GET.get('to', ''))
    except (TypeError, ValueError):
        return JsonResponse({'error': '请选择两个有效版本进行比较'}, status=400)

    revisions = list(
        NoteRevision.objects.select_related('note', 'created_by').filter(
            note_id=note_id,
            id__in=[from_id, to_id],
        )
    )
    if len(revisions) != 2:
        return JsonResponse({'error': '版本不存在'}, status=404)
    note = revisions[0].note
    if not _history_permission(note, request.user):
        return JsonResponse({'error': '无权查看此笔记的版本历史'}, status=403)

    by_id = {item.id: item for item in revisions}
    before = by_id[from_id]
    after = by_id[to_id]
    before_text = BeautifulSoup(before.content or '', 'html.parser').get_text('\n')
    after_text = BeautifulSoup(after.content or '', 'html.parser').get_text('\n')
    diff = '\n'.join(difflib.unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile=f'v{before.version_number}',
        tofile=f'v{after.version_number}',
        lineterm='',
        n=2,
    ))
    return JsonResponse({
        'from': _revision_payload(before),
        'to': _revision_payload(after),
        'title_changed': before.title != after.title,
        'diff': diff,
    })


@login_required
@require_http_methods(['POST'])
def restore_note_revision_api(request, note_id, revision_id):
    revision = get_object_or_404(
        NoteRevision.objects.select_related('note', 'created_by'),
        id=revision_id,
        note_id=note_id,
    )
    note = revision.note
    if not note.has_manage_permission(request.user) or note.is_trashed:
        return JsonResponse({'error': '无权恢复此笔记版本'}, status=403)

    note.title = revision.title
    note.content = revision.content
    note.last_modified_by = request.user
    note.save()
    restored = create_note_revision(note, request.user, action=NoteRevision.ACTION_RESTORED)
    if note.author_id != request.user.id:
        notify_user(
            note.author,
            'note_revision_restored',
            f'{request.user.username} 恢复了笔记版本',
            note.title[:200],
            note_id=note.id,
            revision_id=restored.id,
        )

    return JsonResponse({
        'status': 'restored',
        'revision': _revision_payload(restored),
        'note': {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'toc': note.toc or [],
            'updated_at': timezone.localtime(note.updated_at).strftime('%Y-%m-%d %H:%M'),
        },
    })
