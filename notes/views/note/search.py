"""Notes search views."""
from .common import *  # noqa: F401, F403


@login_required
def search_notes_api(request):
    """【核心修改】搜索逻辑现在只在当前用户的笔记中进行。"""
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse([], safe=False)

    user = request.user
    # 【修改点】查询条件简化：标题或内容包含查询字符串，并且作者是当前用户
    search_condition = Q(title__icontains=query) | Q(content__icontains=query)
    results = (
        Note.objects.filter(
            search_condition,
            Q(author=user) | Q(collaborators__user=user),
            is_secret=False,
            is_trashed=False,
        )
        .distinct()
        .order_by('-updated_at')
        .values('id', 'title')
    )

    return JsonResponse(list(results), safe=False)

@login_required
def get_all_notes_api(request):
    """获取所有笔记（排除保密柜笔记）"""
    user = request.user

    # 直接查询数据库，不依赖缓存
    # 这样可以确保 is_secret 过滤总是准确的
    all_notes = list(
        Note.objects.filter(
            Q(author=user) | Q(collaborators__user=user),
            is_secret=False,  # 排除保密柜笔记
            is_trashed=False
        )
        .distinct()
        .order_by('-updated_at')
        .values('id', 'title', 'is_secret', 'folder_id', 'is_favorited')
    )

    return JsonResponse(all_notes, safe=False)
