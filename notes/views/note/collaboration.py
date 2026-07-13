"""Private note collaboration APIs."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from notes.models import Note, NoteCollaborator


def _serialize_collaborator(collaborator):
    return {
        'id': collaborator.id,
        'role': collaborator.role,
        'user': {
            'id': collaborator.user_id,
            'username': collaborator.user.username,
        },
        'added_at': collaborator.created_at.strftime('%Y-%m-%d %H:%M'),
    }


def _require_manage_permission(note, user):
    if note.is_secret:
        return JsonResponse({'error': '保密笔记不能添加协作者'}, status=400)
    if note.is_trashed:
        return JsonResponse({'error': '请先恢复笔记后再管理协作者'}, status=409)
    if not note.has_manage_permission(user):
        return JsonResponse({'error': '只有笔记所有者或管理员可以管理协作者'}, status=403)
    return None


@login_required
@require_http_methods(['GET', 'POST'])
def note_collaborators_api(request, note_id):
    note = get_object_or_404(Note.objects.select_related('author'), id=note_id)
    if note.is_secret:
        return JsonResponse({'error': '保密笔记不支持协作'}, status=400)
    if request.method == 'GET':
        if not note.has_read_permission(request.user):
            return JsonResponse({'error': '无权访问此笔记'}, status=403)
        collaborators = note.collaborators.select_related('user').order_by('created_at')
        return JsonResponse({
            'note_id': note.id,
            'can_manage': note.has_manage_permission(request.user),
            'current_role': note.collaborator_role_for(request.user),
            'owner': {'id': note.author_id, 'username': note.author.username},
            'collaborators': [_serialize_collaborator(item) for item in collaborators],
        })

    error_response = _require_manage_permission(note, request.user)
    if error_response:
        return error_response
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的 JSON 数据'}, status=400)

    role = data.get('role', NoteCollaborator.ROLE_READER)
    valid_roles = {value for value, _ in NoteCollaborator.ROLE_CHOICES}
    if role not in valid_roles:
        return JsonResponse({'error': '无效的协作权限'}, status=400)

    user_id = data.get('user_id')
    username = str(data.get('username') or '').strip()
    user_model = get_user_model()
    if user_id:
        collaborator_user = get_object_or_404(user_model, id=user_id)
    elif username:
        collaborator_user = get_object_or_404(user_model, username=username)
    else:
        return JsonResponse({'error': '请输入用户名或用户 ID'}, status=400)

    if collaborator_user.id == note.author_id:
        return JsonResponse({'error': '笔记所有者已拥有管理权限'}, status=400)

    collaborator, created = NoteCollaborator.objects.update_or_create(
        note=note,
        user=collaborator_user,
        defaults={'role': role, 'added_by': request.user},
    )
    return JsonResponse({
        'status': 'created' if created else 'updated',
        'collaborator': _serialize_collaborator(collaborator),
    }, status=201 if created else 200)


@login_required
@require_http_methods(['DELETE'])
def note_collaborator_detail_api(request, note_id, collaborator_id):
    note = get_object_or_404(Note, id=note_id)
    error_response = _require_manage_permission(note, request.user)
    if error_response:
        return error_response
    collaborator = get_object_or_404(NoteCollaborator, id=collaborator_id, note=note)
    collaborator.delete()
    return JsonResponse({'status': 'deleted'})
