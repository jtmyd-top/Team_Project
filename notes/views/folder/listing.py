"""Folder listing views."""
from .common import *  # noqa: F401, F403


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

