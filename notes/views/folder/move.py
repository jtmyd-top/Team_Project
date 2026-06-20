"""Folder move views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["POST"])
def move_note_api(request, note_id):
    """移动笔记到指定文件夹"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 格式'}, status=400)
    
    folder_id = data.get('folder_id')
    
    if folder_id is None:
        # 移动到收件箱
        note.folder = None
    else:
        folder = get_object_or_404(Folder, id=folder_id, owner=user)
        note.folder = folder
    
    note.save(update_fields=['folder'])
    cache.delete(get_sidebar_cache_key(user.id))
    
    return JsonResponse({
        'status': 'success',
        'note_id': note.id,
        'folder_id': note.folder_id
    })

@login_required
@require_http_methods(["POST"])
def copy_note_api(request, note_id):
    """Copy the current user's note into inbox or a target folder."""
    user = request.user
    source = get_object_or_404(Note, id=note_id, author=user, is_trashed=False)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    folder_id = data.get('folder_id')
    target_folder = None
    if folder_id is not None:
        target_folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=False)

    copied = Note.objects.create(
        title=source.title,
        content=source.content,
        author=user,
        folder=target_folder,
        last_modified_by=user,
        is_public=False,
        is_favorited=False,
        is_secret=source.is_secret,
    )
    copied.tags.set(source.tags.all())
    copied.save()

    cache.delete(get_sidebar_cache_key(user.id))
    log_action(user, copied, 1, f'Copied note from #{source.id}')

    return JsonResponse({
        'status': 'success',
        'note_id': copied.id,
        'source_note_id': source.id,
        'folder_id': copied.folder_id,
        'note': {
            'id': copied.id,
            'title': copied.title,
            'updated_at': copied.updated_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorited': copied.is_favorited,
            'is_secret': copied.is_secret,
            'folder': {
                'id': copied.folder.id,
                'name': copied.folder.name,
            } if copied.folder else None,
        }
    }, status=201)

