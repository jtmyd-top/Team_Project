"""Comment comments views."""
from .common import *  # noqa: F401, F403
from notes.views.note.common import _invalidate_public_notes_cache


@require_http_methods(["GET"])
def note_comments_api(request, note_id):
    """获取指定公开笔记的评论列表（树形结构：顶级评论 + 回复）"""
    try:
        note = get_object_or_404(Note, id=note_id, is_public=True, is_secret=False, is_trashed=False)
        try:
            page = max(1, int(request.GET.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(1, min(int(request.GET.get('page_size', 20) or 20), 100))
        except (TypeError, ValueError):
            page_size = 20
        total = NoteComment.objects.filter(note=note).count()

        top_comments = NoteComment.objects.filter(
            note=note, parent=None
        ).select_related('author', 'author__profile').prefetch_related(
            'replies__author', 'replies__author__profile'
        ).order_by('created_at')
        top_total = top_comments.count()
        start = (page - 1) * page_size
        end = start + page_size
        top_comments = top_comments[start:end]

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except Exception:
                pass
            return '/static/img/default-avatar.png'

        def serialize_comment(c):
            return {
                'id': c.id,
                'author': c.author.username,
                'author_id': c.author.id,
                'author_avatar': get_avatar(c.author),
                'content': c.content,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
                'is_owner': request.user.is_authenticated and request.user == c.author,
                'replies': [
                    {
                        'id': r.id,
                        'author': r.author.username,
                        'author_id': r.author.id,
                        'author_avatar': get_avatar(r.author),
                        'content': r.content,
                        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
                        'is_owner': request.user.is_authenticated and request.user == r.author,
                    }
                    for r in c.replies.all()
                ]
            }

        data = [serialize_comment(c) for c in top_comments]
        return JsonResponse({
            'comments': data,
            'total': total,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'top_level_total': top_total,
                'top_level_total_pages': max(1, (top_total + page_size - 1) // page_size),
            }
        })
    except Http404:
        raise
    except Exception as e:
        logger.error("获取评论列表失败: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)

@require_http_methods(["POST"])
@login_required
def note_comment_create_api(request, note_id):
    """登录用户为公开笔记发表评论或回复"""
    try:
        comment_ban = UserSanction.is_comment_banned(request.user)
        if comment_ban is not None:
            if comment_ban.expires_at is None:
                message = '你已被禁止发表评论。'
            else:
                message = f'你已被禁止发表评论，限制将于 {comment_ban.expires_at:%Y-%m-%d %H:%M} 解除。'
            return JsonResponse({'error': message, 'message': message}, status=403)

        note = get_object_or_404(Note, id=note_id, is_public=True, is_secret=False, is_trashed=False)
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        parent_id = data.get('parent_id')

        if not content:
            return JsonResponse({'error': '评论内容不能为空'}, status=400)
        if len(content) > 2000:
            return JsonResponse({'error': '评论内容不能超过2000字'}, status=400)

        parent = None
        if parent_id:
            parent = get_object_or_404(NoteComment, id=parent_id, note=note)

        comment = NoteComment.objects.create(
            note=note,
            author=request.user,
            content=content,
            parent=parent
        )
        _invalidate_public_notes_cache()

        if parent and parent.author_id != request.user.id:
            notify_user(
                parent.author,
                'comment_reply',
                f'{request.user.username} 回复了你的评论',
                content,
                note_id=note.id,
                public_id=str(note.public_id),
                comment_id=comment.id,
                parent_comment_id=parent.id,
            )
        if note.author_id != request.user.id and (not parent or parent.author_id != note.author_id):
            notify_user(
                note.author,
                'new_comment',
                f'{request.user.username} 评论了你的笔记',
                content,
                note_id=note.id,
                public_id=str(note.public_id),
                comment_id=comment.id,
            )

        def get_avatar(user):
            try:
                if user.profile.avatar:
                    return user.profile.avatar.url
            except Exception:
                pass
            return '/static/img/default-avatar.png'

        return JsonResponse({
            'id': comment.id,
            'author': comment.author.username,
            'author_id': comment.author.id,
            'author_avatar': get_avatar(comment.author),
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'parent_id': parent_id,
            'is_owner': True,
            'replies': []
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求格式错误'}, status=400)
    except Http404:
        raise
    except Exception as e:
        logger.error("创建评论失败: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)

@require_http_methods(["DELETE"])
@login_required
def note_comment_delete_api(request, comment_id):
    """删除自己发表的评论"""
    try:
        comment = get_object_or_404(NoteComment, id=comment_id)
        if comment.author != request.user and not request.user.is_staff:
            return JsonResponse({'error': '无权删除此评论'}, status=403)
        comment.delete()
        _invalidate_public_notes_cache()
        return JsonResponse({'status': 'deleted'})
    except Http404:
        raise
    except Exception as e:
        logger.error("删除评论失败: %s", e, exc_info=True)
        return JsonResponse({'error': '服务器错误'}, status=500)
