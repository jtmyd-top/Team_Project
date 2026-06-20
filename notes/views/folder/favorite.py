"""Folder favorite views."""
from .common import *  # noqa: F401, F403


@login_required
@require_http_methods(["GET"])
@login_required
@require_http_methods(["GET"])
def favorited_notes_api(request):
    """获取收藏的笔记列表"""
    from bs4 import BeautifulSoup

    user = request.user

    notes = Note.objects.filter(
        author=user,
        is_favorited=True,
        is_trashed=False,
        is_secret=False
    ).order_by('-updated_at').select_related('author', 'author__profile').prefetch_related('tags')

    notes_data = []
    for note in notes:
        # 使用BeautifulSoup安全地提取纯文本摘要
        soup = BeautifulSoup(note.content or "", 'html.parser')
        excerpt = soup.get_text()[:150] + '...'

        # 获取作者头像URL
        author_avatar = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar = profile.avatar.url
            except:
                pass

        notes_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author': note.author.username if note.author else "匿名作者",
            'author_avatar': author_avatar,
            'created_at': note.created_at.isoformat(),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()],
            'views': note.views,
            'comments_count': note.comments.count(),
            'is_favorited': True,
            'user_has_liked': False,
            'likes': 0,
        })

    return JsonResponse(notes_data, safe=False)

@login_required
@require_http_methods(["POST"])
@login_required
@require_http_methods(["POST"])
def toggle_note_favorite_api(request, note_id):
    """切换笔记的收藏状态"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)

    # 【新增】安全檢查：保密柜保護
    allowed, error_msg = check_note_secret_operation_permission(note, 'favorite')
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    note.is_favorited = not note.is_favorited
    note.save(update_fields=['is_favorited'])

    return JsonResponse({
        'status': 'success',
        'is_favorited': note.is_favorited
    })

