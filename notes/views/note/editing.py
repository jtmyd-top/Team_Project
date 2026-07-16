"""Short-lived editing presence for collaborative notes.

This is intentionally a soft reservation. It keeps collaborators from
accidentally overwriting each other while the full CRDT editor remains a
separate future phase.
"""

import json
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from notes.models import Note


EDITING_PRESENCE_TTL_SECONDS = 75
EDITING_PRESENCE_CACHE_TTL_SECONDS = 90


def _presence_cache_key(note_id):
    return f'note_editing_presence:{note_id}'


def _load_active_editors(note):
    now = time.time()
    active = cache.get(_presence_cache_key(note.id), {})
    if not isinstance(active, dict):
        active = {}

    normalized = {}
    for user_id, item in active.items():
        try:
            last_seen = float(item.get('last_seen', 0))
            normalized_user_id = int(user_id)
        except (AttributeError, TypeError, ValueError):
            continue
        if now - last_seen <= EDITING_PRESENCE_TTL_SECONDS:
            normalized[str(normalized_user_id)] = {
                'user_id': normalized_user_id,
                'username': str(item.get('username') or ''),
                'last_seen': last_seen,
            }
    return normalized


def _save_active_editors(note, active):
    key = _presence_cache_key(note.id)
    if active:
        cache.set(key, active, timeout=EDITING_PRESENCE_CACHE_TTL_SECONDS)
    else:
        cache.delete(key)


def _response(note, active, current_user_id):
    editors = sorted(active.values(), key=lambda item: item['username'].lower())
    others = [item for item in editors if item['user_id'] != current_user_id]
    return JsonResponse({
        'note_id': note.id,
        'active_editors': [
            {
                'user_id': item['user_id'],
                'username': item['username'],
                'is_current_user': item['user_id'] == current_user_id,
            }
            for item in editors
        ],
        'editing_by_others': bool(others),
        'editing_by': others[0]['username'] if others else '',
        'heartbeat_seconds': 20,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def note_editing_session_api(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if note.is_secret:
        return JsonResponse({'error': '保密笔记不支持协作编辑'}, status=400)
    if note.is_trashed:
        return JsonResponse({'error': '请先恢复笔记后再编辑'}, status=409)
    if not note.has_read_permission(request.user):
        return JsonResponse({'error': '无权访问此笔记'}, status=403)

    active = _load_active_editors(note)
    if request.method == 'GET':
        _save_active_editors(note, active)
        return _response(note, active, request.user.id)

    if not note.has_write_permission(request.user):
        return JsonResponse({'error': '无权编辑此笔记'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 数据'}, status=400)

    action = payload.get('action', 'heartbeat')
    user_key = str(request.user.id)
    if action in {'enter', 'heartbeat'}:
        active[user_key] = {
            'user_id': request.user.id,
            'username': request.user.username,
            'last_seen': time.time(),
        }
    elif action == 'leave':
        active.pop(user_key, None)
    else:
        return JsonResponse({'error': '无效的编辑会话操作'}, status=400)

    _save_active_editors(note, active)
    return _response(note, active, request.user.id)
