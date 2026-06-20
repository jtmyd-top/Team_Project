"""Folder trash views."""
from .common import *  # noqa: F401, F403


def _annotate_trashed_children(queryset):
    return queryset.annotate(
        trashed_child_folder_count=Count(
            'children',
            filter=Q(children__is_trashed=True),
            distinct=True,
        ),
        trashed_note_count=Count(
            'notes_in_folder',
            filter=Q(notes_in_folder__is_trashed=True),
            distinct=True,
        ),
    )


def _folder_children_count(folder):
    return folder.trashed_child_folder_count + folder.trashed_note_count


@login_required
@require_http_methods(["GET"])
def trashed_items_api(request):
    """Return all trashed folders and top-level trashed notes."""
    user = request.user

    trashed_folders = _annotate_trashed_children(
        Folder.objects.filter(owner=user, is_trashed=True)
    ).order_by('-trashed_at')
    trashed_notes = (
        Note.objects.filter(author=user, is_trashed=True)
        .exclude(folder__is_trashed=True)
        .order_by('-trashed_at')
        .select_related('folder')
    )

    folders_data = [
        {
            'type': 'folder',
            'id': folder.id,
            'name': folder.name,
            'trashed_at': folder.trashed_at.strftime('%Y-%m-%d %H:%M') if folder.trashed_at else None,
            'children_count': _folder_children_count(folder),
            'has_children': _folder_children_count(folder) > 0,
        }
        for folder in trashed_folders
    ]
    notes_data = [
        {
            'type': 'note',
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'is_favorited': note.is_favorited,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name,
            } if note.folder and not note.folder.is_trashed else None,
        }
        for note in trashed_notes
    ]

    all_items = sorted(
        folders_data + notes_data,
        key=lambda item: item['trashed_at'] or '',
        reverse=True,
    )
    return JsonResponse({'items': all_items})


@login_required
@require_http_methods(["GET"])
def trashed_folder_contents_api(request, folder_id):
    """Return trashed notes and subfolders inside a trashed folder."""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)

    notes = folder.notes_in_folder.filter(is_trashed=True).order_by('-trashed_at')
    subfolders = _annotate_trashed_children(
        folder.children.filter(is_trashed=True)
    ).order_by('-trashed_at')

    return JsonResponse({
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'trashed_at': folder.trashed_at.strftime('%Y-%m-%d %H:%M') if folder.trashed_at else None,
        },
        'notes': [
            {
                'type': 'note',
                'id': note.id,
                'title': note.title,
                'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
                'is_secret': note.is_secret,
                'is_trashed': note.is_trashed,
                'is_favorited': note.is_favorited,
            }
            for note in notes
        ],
        'subfolders': [
            {
                'type': 'folder',
                'id': subfolder.id,
                'name': subfolder.name,
                'trashed_at': (
                    subfolder.trashed_at.strftime('%Y-%m-%d %H:%M')
                    if subfolder.trashed_at
                    else None
                ),
                'children_count': _folder_children_count(subfolder),
                'has_children': _folder_children_count(subfolder) > 0,
            }
            for subfolder in subfolders
        ],
    })


@login_required
@require_http_methods(["POST"])
def restore_folder_api(request, folder_id):
    """Restore a trashed folder and its trashed descendants."""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)

    folder.restore_from_trash()
    folder.notes_in_folder.filter(is_trashed=True).update(is_trashed=False, trashed_at=None)

    def restore_children(parent_folder):
        for child in parent_folder.children.filter(is_trashed=True):
            child.restore_from_trash()
            child.notes_in_folder.filter(is_trashed=True).update(is_trashed=False, trashed_at=None)
            restore_children(child)

    restore_children(folder)
    cache.delete(get_sidebar_cache_key(user.id))
    log_action(user, folder, 2, f'恢复回收站文件夹：{folder.name}')

    return JsonResponse({
        'status': 'success',
        'message': '文件夹已恢复',
    })


@login_required
@require_http_methods(["DELETE"])
def permanent_delete_folder_api(request, folder_id):
    """Permanently delete a trashed folder and all descendants."""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)
    folder_name = folder.name

    def count_recursive(current_folder):
        note_count = current_folder.notes_in_folder.count()
        folder_count = 0
        for child in current_folder.children.all():
            folder_count += 1
            child_notes, child_folders = count_recursive(child)
            note_count += child_notes
            folder_count += child_folders
        return note_count, folder_count

    def delete_recursive(folder_to_delete):
        folder_to_delete.notes_in_folder.all().delete()
        for child in folder_to_delete.children.all():
            delete_recursive(child)
        folder_to_delete.delete()

    note_count, child_folder_count = count_recursive(folder)
    detail = f'永久删除文件夹：{folder_name}'
    if child_folder_count or note_count:
        detail += f'，包含 {child_folder_count} 个子文件夹、{note_count} 篇笔记'
    log_action(user, folder, 3, detail)

    delete_recursive(folder)
    cache.delete(get_sidebar_cache_key(user.id))
    return JsonResponse({
        'status': 'success',
        'message': '文件夹已永久删除',
    })


@login_required
@require_http_methods(["GET"])
def trashed_notes_api(request):
    """Return trashed notes outside trashed folders."""
    user = request.user
    notes = (
        Note.objects.filter(author=user, is_trashed=True)
        .exclude(folder__is_trashed=True)
        .order_by('-trashed_at')
        .select_related('folder')
    )

    return JsonResponse({
        'notes': [
            {
                'id': note.id,
                'title': note.title,
                'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
                'is_secret': note.is_secret,
                'is_trashed': note.is_trashed,
                'is_favorited': note.is_favorited,
                'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
                'folder': {
                    'id': note.folder.id,
                    'name': note.folder.name,
                } if note.folder and not note.folder.is_trashed else None,
            }
            for note in notes
        ],
    })


@login_required
@require_http_methods(["POST"])
def trash_note_api(request, note_id):
    """Move a note into trash."""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)

    note.move_to_trash()
    cache.delete(get_sidebar_cache_key(user.id))
    log_action(user, note, 3, f'将笔记移入回收站：{note.title}')

    return JsonResponse({
        'status': 'success',
        'message': '笔记已移入回收站',
    })


@login_required
@require_http_methods(["POST"])
def restore_note_api(request, note_id):
    """Restore a trashed note."""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)

    note.restore_from_trash()
    cache.delete(get_sidebar_cache_key(user.id))
    log_action(user, note, 2, f'恢复笔记：{note.title}')

    return JsonResponse({
        'status': 'success',
        'message': '笔记已恢复',
    })


@login_required
@require_http_methods(["DELETE"])
def permanent_delete_note_api(request, note_id):
    """Permanently delete a trashed note."""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user, is_trashed=True)

    note_title = note.title
    log_action(user, note, 3, f'永久删除笔记：{note_title}')

    note.delete()
    cache.delete(get_sidebar_cache_key(user.id))
    return JsonResponse({
        'status': 'success',
        'message': '笔记已永久删除',
    })
