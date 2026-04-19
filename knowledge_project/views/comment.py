# knowledge_project/views/comment.py
"""笔记评论 API (原 legacy.py 4046-4156 段)"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from ..models import Note, NoteComment

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def note_comments_api(request, note_id):
    """获取指定公开笔记的评论列表（树形结构：顶级评论 + 回复）"""
    try:
        note = get_object_or_404(Note, id=note_id, is_public=True)
        top_comments = NoteComment.objects.filter(
            note=note, parent=None
        ).select_related('author', 'author__profile').prefetch_related('replies__author', 'replies__author__profile')

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
        return JsonResponse({'comments': data, 'total': NoteComment.objects.filter(note=note).count()})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def note_comment_create_api(request, note_id):
    """登录用户为公开笔记发表评论或回复"""
    try:
        note = get_object_or_404(Note, id=note_id, is_public=True)
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["DELETE"])
@login_required
def note_comment_delete_api(request, comment_id):
    """删除自己发表的评论"""
    try:
        comment = get_object_or_404(NoteComment, id=comment_id)
        if comment.author != request.user and not request.user.is_staff:
            return JsonResponse({'error': '无权删除此评论'}, status=403)
        comment.delete()
        return JsonResponse({'status': 'deleted'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
