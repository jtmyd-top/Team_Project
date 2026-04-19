"""
文件夹相关的 API 视图
"""
import json
from django.db import models
from django.db.models import Count, Q, Exists, OuterRef
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from .models import Folder, Note
from .utils.misc import get_sidebar_cache_key, log_action
# 【新增】導入安全檢查函數
from .views import check_note_secret_operation_permission


def build_folder_tree(folders, parent_id=None):
    """递归构建文件夹树（使用预加载的 notes_count）"""
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
                # 使用预加载的 annotated 字段，避免 N+1 查询
                'notes_count': getattr(folder, 'notes_count', 0)
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
        # 使用 annotate 预加载 notes_count，避免 N+1 查询
        folders = Folder.objects.filter(
            owner=user,
            is_trashed=False
        ).annotate(
            notes_count=Count(
                'notes_in_folder',
                filter=Q(notes_in_folder__is_trashed=False, notes_in_folder__is_secret=False)
            )
        ).order_by('order', 'name')
        tree = build_folder_tree(list(folders))
        
        # 获取收件箱笔记数量
        inbox_count = Note.objects.filter(
            author=user,
            folder__isnull=True,
            is_trashed=False,
            is_secret=False  # 排除保密柜笔记
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

        log_action(user, folder, 1, f'创建文件夹「{folder.name}」')

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

    if request.method == 'GET':
        # 使用 annotate 获取 notes_count，避免额外查询
        folder = Folder.objects.filter(
            id=folder_id,
            owner=user
        ).annotate(
            notes_count=Count(
                'notes_in_folder',
                filter=Q(notes_in_folder__is_trashed=False, notes_in_folder__is_secret=False)
            )
        ).first()

        if not folder:
            return JsonResponse({'error': '文件夹不存在'}, status=404)

        return JsonResponse({
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'order': folder.order,
            'notes_count': folder.notes_count
        })

    # PUT 和 DELETE 请求使用普通查询
    folder = get_object_or_404(Folder, id=folder_id, owner=user)

    if request.method == 'PUT':
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

        log_action(user, folder, 2, f'修改文件夹「{folder.name}」')

        return JsonResponse({
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'order': folder.order
        })

    elif request.method == 'DELETE':
        # 【修复】将文件夹移入回收站，而不是直接删除
        # 统计受影响的子文件夹和笔记数量
        descendants = list(folder.get_descendants())
        child_folder_count = len(descendants)
        note_count = folder.notes_in_folder.count()
        for child in descendants:
            note_count += child.notes_in_folder.count()

        # 将文件夹及其所有子文件夹标记为已删除
        folder.move_to_trash()

        # 递归将所有子文件夹也移入回收站
        for child in descendants:
            child.move_to_trash()

        # 同时将文件夹内的所有笔记移入回收站
        folder.notes_in_folder.update(is_trashed=True)

        # 递归将子文件夹内的笔记也移入回收站
        for child in descendants:
            child.notes_in_folder.update(is_trashed=True)

        cache.delete(get_sidebar_cache_key(user.id))

        detail = f'移入回收站「{folder.name}」'
        if child_folder_count > 0 or note_count > 0:
            detail += f'（含 {child_folder_count} 个子文件夹、{note_count} 篇笔记）'
        log_action(user, folder, 3, detail)

        return JsonResponse({'status': 'success', 'message': '文件夹已移入回收站'})


@login_required
@require_http_methods(["GET"])
def folder_notes_api(request, folder_id):
    """获取文件夹下的笔记列表和子文件夹"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user)

    # 获取该文件夹下的直接笔记
    notes = folder.notes_in_folder.filter(is_trashed=False, is_secret=False).order_by('-updated_at')

    # 获取该文件夹的直接子文件夹（使用 annotate 避免 N+1 查询）
    subfolders = Folder.objects.filter(
        owner=user,
        parent=folder,
        is_trashed=False
    ).annotate(
        notes_count=Count(
            'notes_in_folder',
            filter=Q(notes_in_folder__is_trashed=False, notes_in_folder__is_secret=False)
        ),
        has_children=Exists(Folder.objects.filter(parent=OuterRef('pk'), is_trashed=False))
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
            'notes_count': sf.notes_count,
            'has_children': sf.has_children
        } for sf in subfolders],
        'notes': [{
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorited': note.is_favorited,
            'is_secret': note.is_secret  # 添加保密标志
        } for note in notes]
    })


@login_required
@require_http_methods(["GET"])
def inbox_notes_api(request):
    """获取收件箱中的笔记（没有分配文件夹的笔记，排除保密笔记）"""
    user = request.user

    notes = Note.objects.filter(
        author=user,
        folder__isnull=True,
        is_secret=False,  # 排除保密笔记
        is_trashed=False
    ).order_by('-updated_at')

    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'is_favorited': note.is_favorited,
            'is_secret': note.is_secret
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
            is_trashed=False,
            is_secret=False  # 排除保密柜笔记
        ).order_by('-created_at').select_related('folder')

        return JsonResponse({
            'notes': [{
                'id': note.id,
                'title': note.title,
                'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
                'is_favorited': note.is_favorited,
                'is_secret': note.is_secret,  # 添加 is_secret 字段
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
@require_http_methods(["GET"])
def trashed_items_api(request):
    """获取回收站中的所有项目（文件夹 + 笔记）"""
    user = request.user

    # 获取被删除的文件夹
    trashed_folders = Folder.objects.filter(
        owner=user,
        is_trashed=True
    ).order_by('-trashed_at')

    # 获取被删除的笔记（排除那些在已删除文件夹中的笔记）
    trashed_notes = Note.objects.filter(
        author=user,
        is_trashed=True
    ).exclude(
        folder__is_trashed=True  # 【关键】不显示已删除文件夹内的笔记
    ).order_by('-trashed_at').select_related('folder')

    folders_data = []
    for folder in trashed_folders:
        folders_data.append({
            'type': 'folder',
            'id': folder.id,
            'name': folder.name,
            'trashed_at': folder.trashed_at.strftime('%Y-%m-%d %H:%M') if folder.trashed_at else None,
            'children_count': folder.get_trashed_children_count(),  # 包含的项目数
            'has_children': folder.children.filter(is_trashed=True).exists() or \
                           folder.notes_in_folder.filter(is_trashed=True).exists()
        })

    notes_data = []
    for note in trashed_notes:
        notes_data.append({
            'type': 'note',
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'is_favorited': note.is_favorited,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name
            } if note.folder and not note.folder.is_trashed else None
        })

    # 合并并按删除时间排序
    all_items = sorted(
        folders_data + notes_data,
        key=lambda x: x['trashed_at'] or '',
        reverse=True
    )

    return JsonResponse({
        'items': all_items
    })


@login_required
@require_http_methods(["GET"])
def trashed_folder_contents_api(request, folder_id):
    """获取回收站中被删除文件夹的内容"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)

    # 获取该文件夹内被删除的笔记
    notes = folder.notes_in_folder.filter(is_trashed=True).order_by('-trashed_at')

    # 获取该文件夹内被删除的子文件夹
    subfolders = folder.children.filter(is_trashed=True).order_by('-trashed_at')

    return JsonResponse({
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'trashed_at': folder.trashed_at.strftime('%Y-%m-%d %H:%M') if folder.trashed_at else None,
        },
        'notes': [{
            'type': 'note',
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'is_favorited': note.is_favorited
        } for note in notes],
        'subfolders': [{
            'type': 'folder',
            'id': sf.id,
            'name': sf.name,
            'trashed_at': sf.trashed_at.strftime('%Y-%m-%d %H:%M') if sf.trashed_at else None,
            'children_count': sf.get_trashed_children_count(),
            'has_children': sf.children.filter(is_trashed=True).exists() or \
                           sf.notes_in_folder.filter(is_trashed=True).exists()
        } for sf in subfolders]
    })


@login_required
@require_http_methods(["POST"])
def restore_folder_api(request, folder_id):
    """从回收站恢复文件夹及其内容"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)

    # 恢复文件夹本身
    folder.restore_from_trash()

    # 同时恢复文件夹内的所有笔记和子文件夹
    folder.notes_in_folder.filter(is_trashed=True).update(
        is_trashed=False,
        trashed_at=None
    )

    # 递归恢复子文件夹
    def restore_children(parent_folder):
        for child in parent_folder.children.filter(is_trashed=True):
            child.restore_from_trash()
            # 恢复子文件夹内的笔记
            child.notes_in_folder.filter(is_trashed=True).update(
                is_trashed=False,
                trashed_at=None
            )
            restore_children(child)

    restore_children(folder)

    cache.delete(get_sidebar_cache_key(user.id))

    log_action(user, folder, 2, f'从回收站恢复文件夹「{folder.name}」及其内容')

    return JsonResponse({
        'status': 'success',
        'message': '文件夹及内容已恢复'
    })


@login_required
@require_http_methods(["DELETE"])
def permanent_delete_folder_api(request, folder_id):
    """永久删除文件夹及其内容"""
    user = request.user
    folder = get_object_or_404(Folder, id=folder_id, owner=user, is_trashed=True)

    # 统计受影响的内容（删除前记录）
    folder_name = folder.name

    def count_recursive(f):
        notes = f.notes_in_folder.count()
        folders = 0
        for child in f.children.all():
            folders += 1
            cn, cf = count_recursive(child)
            notes += cn
            folders += cf
        return notes, folders

    note_count, child_folder_count = count_recursive(folder)

    # 递归删除所有子文件夹和笔记
    def delete_folder_recursive(folder_to_delete):
        # 先删除所有笔记
        folder_to_delete.notes_in_folder.all().delete()
        # 递归删除子文件夹
        for child in folder_to_delete.children.all():
            delete_folder_recursive(child)
        # 最后删除文件夹本身
        folder_to_delete.delete()

    # 先记录日志（删除后对象不存在了）
    detail = f'永久删除文件夹「{folder_name}」'
    if child_folder_count > 0 or note_count > 0:
        detail += f'（含 {child_folder_count} 个子文件夹、{note_count} 篇笔记）'
    log_action(user, folder, 3, detail)

    delete_folder_recursive(folder)

    cache.delete(get_sidebar_cache_key(user.id))

    return JsonResponse({
        'status': 'success',
        'message': '文件夹已永久删除'
    })


@login_required
@require_http_methods(["GET"])
def trashed_notes_api(request):
    """获取回收站中的笔记列表（保留用于向后兼容）"""
    user = request.user

    notes = Note.objects.filter(
        author=user,
        is_trashed=True
    ).exclude(
        folder__is_trashed=True
    ).order_by('-trashed_at').select_related('folder')

    return JsonResponse({
        'notes': [{
            'id': note.id,
            'title': note.title,
            'trashed_at': note.trashed_at.strftime('%Y-%m-%d %H:%M') if note.trashed_at else None,
            'is_secret': note.is_secret,
            'is_trashed': note.is_trashed,
            'is_favorited': note.is_favorited,
            'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M'),
            'folder': {
                'id': note.folder.id,
                'name': note.folder.name
            } if note.folder and not note.folder.is_trashed else None
        } for note in notes]
    })


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


@login_required
@require_http_methods(["POST"])
def trash_note_api(request, note_id):
    """将笔记移入回收站"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)

    note.move_to_trash()
    cache.delete(get_sidebar_cache_key(user.id))

    log_action(user, note, 3, f'移入回收站「{note.title}」')

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

    log_action(user, note, 2, f'从回收站恢复「{note.title}」')

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

    note_title = note.title
    log_action(user, note, 3, f'永久删除笔记「{note_title}」')

    note.delete()
    cache.delete(get_sidebar_cache_key(user.id))

    return JsonResponse({
        'status': 'success',
        'message': '笔记已永久删除'
    })
