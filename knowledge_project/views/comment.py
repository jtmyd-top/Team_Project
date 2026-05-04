# knowledge_project/views/comment.py
"""笔记评论 API (原 legacy.py 4046-4156 段)"""
import json
import logging
import hashlib
import re
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
import requests

from ..models import Note, NoteComment

logger = logging.getLogger(__name__)

QQ_MUSIC_HOSTS = {'c6.y.qq.com', 'i.y.qq.com', 'y.qq.com'}


def _extract_first_url(raw_value):
    match = re.search(r'https?://[^\s<>"\']+', str(raw_value or ''), re.I)
    return match.group(0) if match else ''


def _compact_qqmusic_text(raw_value):
    return re.sub(r'\s+', '', str(raw_value or ''))


def _is_allowed_qqmusic_url(raw_url):
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and parsed.hostname in QQ_MUSIC_HOSTS


def _extract_qqmusic_ids(raw_value):
    text = str(raw_value or '')
    compact_text = _compact_qqmusic_text(text)

    direct_songmid = re.fullmatch(r'[A-Za-z0-9]{8,32}', text.strip())
    if direct_songmid and not text.strip().isdigit():
        return {'player_id': direct_songmid.group(0), 'id_type': 'songmid'}

    songid = re.search(r'(?:songid|songId|id)=(\d+)', text, re.I)
    if songid:
        return {'player_id': songid.group(1), 'id_type': 'songid'}
    songid = re.search(r'(?:songid|songId|id)=(\d+)', compact_text, re.I)
    if songid:
        return {'player_id': songid.group(1), 'id_type': 'songid'}

    songmid = re.search(r'(?:songmid|songMid|mid)=([A-Za-z0-9]+)', text, re.I)
    if songmid:
        return {'player_id': songmid.group(1), 'id_type': 'songmid'}
    songmid = re.search(r'(?:songmid|songMid|mid)=([A-Za-z0-9]+)', compact_text, re.I)
    if songmid:
        return {'player_id': songmid.group(1), 'id_type': 'songmid'}

    song_detail = re.search(r'/songDetail/([A-Za-z0-9]+)', text, re.I)
    if song_detail:
        return {'player_id': song_detail.group(1), 'id_type': 'songmid'}
    song_detail = re.search(r'/songDetail/([A-Za-z0-9]+)', compact_text, re.I)
    if song_detail:
        return {'player_id': song_detail.group(1), 'id_type': 'songmid'}

    return None


def _resolve_songid_from_songmid(songmid):
    cache_key = 'qqmusic_songmid:' + hashlib.sha256(str(songmid).encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        response = requests.get(
            f'https://i.y.qq.com/v8/playsong.html?songmid={songmid}&type=0',
            allow_redirects=True,
            timeout=8,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        )
    except requests.RequestException as exc:
        logger.warning('resolve songid from songmid failed: %s', exc)
        return None

    match = (
        re.search(r'"songid"\s*:\s*(\d+)', response.text, re.I)
        or re.search(r'"id"\s*:\s*(\d+)', response.text, re.I)
        or re.search(r'songid=(\d+)', response.text, re.I)
    )
    if not match:
        return None

    songid = match.group(1)
    cache.set(cache_key, songid, 86400)
    return songid


def _resolve_qqmusic_share_payload(raw_text):
    direct_ids = _extract_qqmusic_ids(raw_text)
    if direct_ids:
        if direct_ids['id_type'] == 'songid':
            return {'player_id': direct_ids['player_id'], 'id_type': 'songid'}, None

        resolved_songid = _resolve_songid_from_songmid(direct_ids['player_id'])
        if resolved_songid:
            return {'player_id': resolved_songid, 'id_type': 'songid'}, None
        return None, '未能从 songmid 换算出 songid'

    share_url = _extract_first_url(raw_text)
    if not share_url:
        share_url = _extract_first_url(_compact_qqmusic_text(raw_text))
    if not share_url or not _is_allowed_qqmusic_url(share_url):
        return None, '无效的 QQ 音乐分享链接'

    cache_key = 'qqmusic_share:' + hashlib.sha256(share_url.encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached, None

    try:
        response = requests.get(
            share_url,
            allow_redirects=True,
            timeout=8,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        )
    except requests.RequestException as exc:
        logger.warning('resolve qqmusic share failed: %s', exc)
        return None, 'QQ 音乐短链解析失败'

    candidates = [response.url, response.text]
    candidates.extend(history.url for history in response.history if getattr(history, 'url', None))

    for candidate in candidates:
        resolved = _extract_qqmusic_ids(candidate)
        if resolved:
            if resolved['id_type'] == 'songid':
                cache.set(cache_key, resolved, 86400)
                return resolved, None

            resolved_songid = _resolve_songid_from_songmid(resolved['player_id'])
            if resolved_songid:
                final_payload = {'player_id': resolved_songid, 'id_type': 'songid'}
                cache.set(cache_key, final_payload, 86400)
                return final_payload, None

    return None, '未能从分享链接中提取歌曲信息'


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


@require_http_methods(["GET"])
def resolve_qqmusic_share_api(request):
    try:
        raw_text = request.GET.get('text', '').strip() or request.GET.get('url', '').strip()
        if not raw_text:
            return JsonResponse({'error': '缺少分享内容'}, status=400)

        resolved, error = _resolve_qqmusic_share_payload(raw_text)
        if error:
            return JsonResponse({'error': error}, status=400)

        return JsonResponse({'ok': True, **resolved})
    except Exception as exc:
        logger.error('resolve_qqmusic_share_api failed: %s', exc, exc_info=True)
        return JsonResponse({'error': 'QQ 音乐解析失败'}, status=500)
