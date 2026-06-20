"""Notes public views."""
from .common import *  # noqa: F401, F403
from .common import _coerce_non_negative_int, _get_public_notes_cache_version


def public_note_view(request, public_id):
    try:
        note = Note.objects.get(public_id=public_id, is_public=True, is_trashed=False)
        # 原子递增，避免并发访问时丢失计数
        Note.objects.filter(pk=note.pk).update(views=F('views') + 1)
        note.refresh_from_db(fields=['views'])

        # 获取所有公开文章的导航数据
        all_public_notes = Note.objects.filter(
            is_public=True,
            is_trashed=False,
        ).select_related('author').order_by('-updated_at')

        # 构建导航列表
        navigation_list = []
        for nav_note in all_public_notes:
            navigation_list.append({
                'public_id': str(nav_note.public_id),
                'title': nav_note.title,
                'public_url': f"/notes/public/{nav_note.public_id}/"
            })

        # 找到当前文章在列表中的位置
        current_index = -1
        for i, nav_item in enumerate(navigation_list):
            if nav_item['public_id'] == str(note.public_id):
                current_index = i
                break

        # 获取上一篇文章和下一篇文章
        previous_note = None
        next_note = None

        if current_index > 0:
            previous_note = navigation_list[current_index - 1]
        if current_index < len(navigation_list) - 1:
            next_note = navigation_list[current_index + 1]

        # 获取作者头像信息
        author_avatar_url = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar_url = profile.avatar.url
            except Profile.DoesNotExist:
                pass

        # 获取用户点赞状态和总点赞数
        user_has_liked = False
        total_likes = 0
        if request.user.is_authenticated:
            user_has_liked = ProfileLike.objects.filter(liker=request.user, profile__user=note.author).exists()
        total_likes = ProfileLike.objects.filter(profile__user=note.author).count()

        # 获取标签
        note_tags = [tag.name for tag in note.tags.all()]

        # 获取评论数
        comment_count = NoteComment.objects.filter(note=note).count()

        # 获取作者笔记数
        author_note_count = Note.objects.filter(
            author=note.author,
            is_public=True,
            is_trashed=False,
        ).count()

        context = {
            'note_data': {
                'id': note.id,
                'public_id': str(note.public_id),
                'title': note.title,
                'author': {
                    'id': note.author.id if note.author else None,
                    'username': note.author.username if note.author else '匿名作者',
                    'avatar_url': author_avatar_url,
                    'note_count': author_note_count,
                },
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
                'views': note.views,
                'likes': total_likes,
                'user_has_liked': user_has_liked,
                'tags': note_tags,
                'toc': note.toc or [],
                'comment_count': comment_count,
            },
            'full_content_data': note.content or "",
            'navigation_data': {
                'previous_note': previous_note,
                'next_note': next_note,
                'navigation_list': navigation_list[:5],
                'likes': total_likes,
                'user_has_liked': user_has_liked,
                'is_authenticated': request.user.is_authenticated
            }
        }
        return render(request, 'knowledge/public_note_view.html', context)

    except Note.DoesNotExist:
        # 如果笔记不存在或非公开，返回一个提示页面
        return render(request, 'knowledge/public_note_view.html', {'error_message': '抱歉，这篇笔记不存在或未公开分享。'})
    except Http404:
        raise
    except Exception as e:
        # 记录未预料到的错误
        print(f"Error in public_note_view for public_id {public_id}: {e}")
        return render(request, 'knowledge/public_note_view.html', {'error_message': '加载笔记时发生了一个错误，请稍后重试。'})

@login_required
def toggle_note_like(request):
    """
    切换笔记作者点赞状态
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '仅支持POST请求'}, status=405)

    try:
        data = json.loads(request.body)
        note_id = data.get('note_id')

        if not note_id:
            return JsonResponse({'status': 'error', 'message': '笔记ID缺失'}, status=400)

        note = Note.objects.select_related('author__profile').get(
            id=note_id,
            is_public=True,
            is_trashed=False,
        )

        # 获取作者的profile
        try:
            author_profile = note.author.profile
        except Profile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '作者资料不存在'}, status=404)

        # 检查用户是否已经点赞过
        existing_like = ProfileLike.objects.filter(
            liker=request.user,
            profile=author_profile
        ).first()

        if existing_like:
            # 如果已点赞，则取消点赞
            existing_like.delete()
            action = 'unliked'
            user_has_liked = False
        else:
            # 如果未点赞，则添加点赞
            ProfileLike.objects.create(
                liker=request.user,
                profile=author_profile
            )
            if request.user != note.author:
                notify_user(
                    note.author,
                    'profile_liked',
                    f'{request.user.username} 点赞了你的主页',
                    note.title,
                    note_id=note.id,
                    public_id=str(note.public_id),
                    liker_id=request.user.id,
                    liker_username=request.user.username,
                )
            action = 'liked'
            user_has_liked = True

        # 计算新的点赞数
        total_likes = ProfileLike.objects.filter(profile__user=note.author).count()

        return JsonResponse({
            'status': 'success',
            'action': action,
            'total_likes': total_likes,
            'user_has_liked': user_has_liked
        })

    except Note.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '笔记不存在'}, status=404)
    except Http404:
        raise
    except Exception as e:
        print(f"Error in toggle_note_like: {e}")
        return JsonResponse({'status': 'error', 'message': '服务器内部错误'}, status=500)

def public_notes_api(request):
    """
    返回公开笔记列表；默认保持兼容，也支持分页参数。

    性能优化:
    - 使用 annotate(Count) 预计算评论数，避免N+1查询
    - 添加Redis缓存（5分钟），减少数据库压力
    - 缓存BeautifulSoup解析结果
    """
    page = _coerce_non_negative_int(request.GET.get('page')) or 1
    page_size = _coerce_non_negative_int(request.GET.get('page_size')) or 50
    page_size = max(1, min(page_size, 100))

    # 构建缓存键（匿名用户和登录用户分开缓存）
    cache_version = _get_public_notes_cache_version()
    cache_key = f"public_notes_api:v{cache_version}:page_{page}:size_{page_size}:user_{request.user.id if request.user.is_authenticated else 'anon'}"

    # 尝试从缓存获取
    cached_response = cache.get(cache_key)
    if cached_response:
        return JsonResponse(cached_response)

    # 优化查询：使用 annotate 预计算评论数，避免N+1问题
    notes_qs = (
        Note.objects
        .filter(is_public=True, is_trashed=False)
        .select_related('author', 'author__profile')
        .prefetch_related('tags')
        .annotate(comments_count_cached=Count('comments'))  # 预计算评论数
        .order_by('-updated_at')
    )

    total = notes_qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    notes_page = notes_qs[start:end]

    # 预加载当前用户的点赞记录
    user_liked_profile_ids = set()
    if request.user.is_authenticated:
        user_liked_profile_ids = set(
            ProfileLike.objects.filter(liker=request.user).values_list('profile_id', flat=True)
        )

    notes_data = []
    for note in notes_page:
        # 使用BeautifulSoup安全地提取纯文本摘要
        soup = BeautifulSoup(note.content or "", 'html.parser')
        excerpt = soup.get_text()[:150] + '...'  # 截取前150个字符作为摘要

        # 获取作者头像URL
        author_avatar = None
        if note.author:
            try:
                profile = note.author.profile
                if profile.avatar:
                    author_avatar = profile.avatar.url
            except:
                pass

        # 获取点赞数据
        likes_count = 0
        author_profile_id = None
        if note.author:
            try:
                likes_count = note.author.profile.likes_count
                author_profile_id = note.author.profile.id
            except:
                pass

        notes_data.append({
            'id': note.id,
            'title': note.title,
            'public_url': f"/notes/public/{note.public_id}/",
            'author_id': note.author.id if note.author else None,
            'author': note.author.username if note.author else "匿名作者",
            'author_avatar': author_avatar,
            'updated_at': note.updated_at.strftime("%Y年%m月%d日"),
            'created_at': note.updated_at.isoformat(),
            'excerpt': excerpt,
            'tags': [tag.name for tag in note.tags.all()],
            'views': note.views,
            'likes': likes_count,
            'user_has_liked': author_profile_id in user_liked_profile_ids if author_profile_id else False,
            'comments_count': note.comments_count_cached,  # 使用预计算的值
            'is_favorited': note.is_favorited,
        })

    response_data = {
        'notes': notes_data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': max(1, (total + page_size - 1) // page_size),
        }
    }

    # 缓存结果5分钟
    cache.set(cache_key, response_data, timeout=300)

    return JsonResponse(response_data)

def public_notes_list_view(request):
    """
    【修正版】
    此视图现在只负责渲染承载Vue应用的HTML空壳，所有数据由JS通过API加载。
    """
    # 不再需要进行分页或查询数据，直接渲染模板
    return render(request, 'knowledge/public_notes_list.html')
