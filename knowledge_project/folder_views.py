"""
文件夹相关的 API 视图
"""
import json
from django.db import models
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from .models import Folder, Note
from .utilt import get_sidebar_cache_key


def build_folder_tree(folders, parent_id=None):
    """递归构建文件夹树"""
    tree = []
    for folder in folders:
        if folder.parent_id == parent_id:
            children = build_folder_tree(folders, folder.id)
            tree.append({
                'id': folder.id,
                'name': folder.name,
                'parent_id': folder.parent_id,
                'order': folder.order,
                'children': children,
                'notes_count': folder.notes_in_folder.filter(is_trashed=False).count()
            })
    return tree


@login_required
@require_http_methods(["GET", "POST"])
def folder_list_api(request):
    """
    GET: 获取当前用户的所有文件夹（树形结构）
    POST: 创建新文件夹
    """
    user = request.user

    if request.method == 'GET':
        folders = Folder.objects.filter(owner=user).order_by('order', 'name')
        tree = build_folder_tree(list(folders))
        
        # 获取收件箱笔记数量
        inbox_count = Note.objects.filter(
            author=user, 
            folder__isnull=True, 
            is_trashed=False
        ).count()
        
        return JsonResponse({
            'folders': tree,
            'inbox_count': inbox_count
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的 JSON 格式'}, status=400)

        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': '文件夹名称不能为空'}, status=400)

        parent_id = data.get('parent_id')
        parent = None
        if parent_id:
            parent = get_object_or_404(Folder, id=parent_id, owner=user)

        # 获取同级文件夹的最大 order
        siblings = Folder.objects.filter(owner=user, parent=parent)
        max_order = siblings.aggregate(max_order=models.Max('order'))['max_order'] or 0

        folder = Folder.objects.create(
            name=name,
            owner=user,
            parent=parent,
            order=max_order + 1
        )

        return JsonResponse({
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'order': folder.order,
            'children': [],
            'notes_count': 0
        }, status=201)


@login_required
@require_http_methods(["GET", "PUT", "DELETE"])
def folder_detail_api(request, folder_id):
    """
    GET: 获取文件夹详情
    PUT: 更新文件夹（重命名）
    DELETE: 删除文件夹（笔记移动到收件箱）
    """
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user)

    if request.method == 'GET':
        return JsonResponse({
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'order': folder.order,
            'notes_count': folder.notes_in_folder.filter(is_trashed=False).count()
        })

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的 JSON 格式'}, status=400)

        name = data.get('name', '').strip()
        if name:
            folder.name = name

        if 'parent_id' in data:
            parent_id = data['parent_id']
            if parent_id is None:
                folder.parent = None
            else:
                # 防止循环引用
                new_parent = get_object_or_404(Folder, id=parent_id, owner=user)
                if new_parent.id != folder.id and folder.id not in [f.id for f in new_parent.get_ancestors()]:
                    folder.parent = new_parent

        if 'order' in data:
            folder.order = int(data['order'])

        folder.save()

        return JsonResponse({
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'order': folder.order
        })

    elif request.method == 'DELETE':
        # 将文件夹内的笔记移动到收件箱
        folder.notes_in_folder.update(folder=None)
        
        # 递归删除子文件夹的笔记也移到收件箱
        for child in folder.get_descendants():
            child.notes_in_folder.update(folder=None)
        
        folder.delete()
        cache.delete(get_sidebar_cache_key(user.id))
        
        return JsonResponse({'status': 'success', 'message': '文件夹已删除'})


@login_required
@require_http_methods(["GET"])
def folder_notes_api(request, folder_id):
    """获取文件夹下的笔记列表和子文件夹"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user)

    # 获取该文件夹下的直接笔记
    notes = folder.notes_in_folder.filter(is_trashed=False).order_by('-updated_at')

    # 获取该文件夹的直接子文件夹
    subfolders = Folder.objects.filter(
        owner=user,
        parent=folder
    ).order_by('order', 'name')

    return JsonResponse({
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id
        },
        'subfolders': [{
            'id': sf.id,
            'name': sf.name,
            'notes_count': sf.notes_in_folder.filter(is_trashed=False).count(),
            'has_children': sf.children.exists()
        } for sf in subfolders],
        'notes': [{
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorited': note.is_favorited
        } for note in notes]
    })


@login_required
@require_http_methods(["GET"])
def inbox_notes_api(request):
    """获取收件箱中的笔记（没有分配文件夹的笔记）"""
    user = request.user
    
    notes = Note.objects.filter(
        author=user, 
        folder__isnull=True, 
        is_trashed=False
    ).order_by('-updated_at')
    
    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorited': note.is_favorited
        } for note in notes]
    })


@login_required
@require_http_methods(["GET"])
def folder_breadcrumb_api(request, folder_id):
    """获取文件夹的面包屑路径"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user)
    
    breadcrumb = [{'id': f.id, 'name': f.name} for f in folder.get_ancestors()]
    breadcrumb.append({'id': folder.id, 'name': folder.name})
    
    return JsonResponse({'breadcrumb': breadcrumb})


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
@require_http_methods(["GET"])
def all_notes_flat_api(request):
    """获取所有笔记的扁平列表（用于全部笔记视图）"""
    try:
        user = request.user
        
        notes = Note.objects.filter(
            author=user, 
            is_trashed=False
        ).order_by('-created_at').select_related('folder')
        
        return JsonResponse({
            'notes': [{
                'id': note.id,
                'title': note.title,
                'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
                'is_favorited': note.is_favorited,
                'folder': {
                    'id': note.folder.id,
                    'name': note.folder.name
                } if note.folder else None
            } for note in notes]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'获取笔记列表失败: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET"])
def favorited_notes_api(request):
    """获取收藏的笔记列表"""
    user = request.user
    
    notes = Note.objects.filter(
        author=user, 
        is_favorited=True,
        is_trashed=False
    ).order_by('-updated_at').select_related('folder')
    
    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name
            } if note.folder else None
        } for note in notes]
    })


@login_required
@require_http_methods(["GET"])
def trashed_notes_api(request):
    """获取回收站中的笔记列表"""
    user = request.user
    
    notes = Note.objects.filter(
        author=user, 
        is_trashed=True
    ).order_by('-trashed_at').select_related('folder')
    
    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name
            } if note.folder else None
        } for note in notes]
    })


@login_required
@require_http_methods(["POST"])
def toggle_note_favorite_api(request, note_id):
    """切换笔记的收藏状态"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)
    
    note.is_favorited = not note.is_favorited
    note.save(update_fields=['is_favorited'])
    
    return JsonResponse({
        'status': 'success',
        'is_favorited': note.is_favorited
    })


@login_required
@require_http_methods(["POST"])
def trash_note_api(request, note_id):
    """将笔记移入回收站"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)
    
    note.move_to_trash()
    cache.delete(get_sidebar_cache_key(user.id))
    
    return JsonResponse({
        'status': 'success',
        'message': '笔记已移入回收站'
    })


@login_required
@require_http_methods(["POST"])
def restore_note_api(request, note_id):
    """从回收站恢复笔记"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)
    
    note.restore_from_trash()
    cache.delete(get_sidebar_cache_key(user.id))
    
    return JsonResponse({
        'status': 'success',
        'message': '笔记已恢复'
    })


@login_required
@require_http_methods(["DELETE"])
def permanent_delete_note_api(request, note_id):
    """永久删除笔记"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user, is_trashed=True)
    
    note.delete()
    cache.delete(get_sidebar_cache_key(user.id))
    
    return JsonResponse({
        'status': 'success',
        'message': '笔记已永久删除'
    })
