"""Notes history views."""
from .common import *  # noqa: F401, F403


def _note_history_cache_key(user_id):
    return f"note_history_api:user_{user_id}"


@login_required
@require_http_methods(["GET"])
def note_history_api(request):
    """
    获取用户的笔记浏览历史

    性能优化:
    - 使用 annotate 预计算评论数
    - 添加缓存（3分钟）
    """
    from notes.models import NoteHistory

    user = request.user

    # 缓存键
    cache_key = _note_history_cache_key(user.id)
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data, safe=False)

    # 优化查询：预计算评论数
    history = (
        NoteHistory.objects
        .filter(
            user=user,
            note__is_public=True,
            note__is_secret=False,
            note__is_trashed=False,
        )
        .select_related('note', 'note__author', 'note__author__profile')
        .prefetch_related('note__tags')
        .annotate(comments_count_cached=Count('note__comments'))
        .order_by('-viewed_at')[:100]
    )

    history_data = []
    for item in history:
        note = item.note
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

        history_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author': note.author.username if note.author else "匿名作者",
            'author_avatar': author_avatar,
            'created_at': note.created_at.isoformat(),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()],
            'views': note.views,
            'comments_count': item.comments_count_cached,  # 使用预计算的值
            'is_favorited': note.is_favorited,
            'user_has_liked': False,
        })

    # 缓存3分钟
    cache.set(cache_key, history_data, timeout=180)

    return JsonResponse(history_data, safe=False)

@login_required
@require_http_methods(["POST"])
def record_note_history_api(request):
    """记录用户浏览笔记的历史"""
    from notes.models import NoteHistory

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 格式'}, status=400)

    note_id = data.get('note_id')
    if not note_id:
        return JsonResponse({'error': '缺少 note_id 参数'}, status=400)

    try:
        note = Note.objects.get(id=note_id, is_public=True, is_secret=False, is_trashed=False)
    except Note.DoesNotExist:
        return JsonResponse({'error': '笔记不存在或不是公开笔记'}, status=404)

    user = request.user
    # 使用 update_or_create 来更新或创建历史记录
    history, created = NoteHistory.objects.update_or_create(
        user=user,
        note=note,
        defaults={'viewed_at': timezone.now()}
    )
    cache.delete(_note_history_cache_key(user.id))

    return JsonResponse({
        'status': 'success',
        'message': '浏览历史已记录'
    })
