"""Notes pages views."""
from .common import *  # noqa: F401, F403


def home_view(request):
    """
    首页视图 - 展示所有公开的文章
    """
    # 获取所有公开的文章，按更新时间倒序排列
    articles = Note.objects.filter(
        is_public=True,
        is_trashed=False,
    ).select_related('author').prefetch_related('tags').order_by('-updated_at')[:20]

    context = {
        'articles': articles
    }
    return render(request, 'home.html', context)

@login_required
def knowledge_list(request):
    """【核心修改】此视图现在只加载当前用户作为作者的笔记。"""
    user = request.user
    # 使用辅助函数生成缓存键 (函数本身无需修改)
    sidebar_notes_key = get_sidebar_cache_key(user.id)
    sidebar_notes = cache.get(sidebar_notes_key)

    if sidebar_notes is None:
        # 【修改点】查询逻辑极大简化：只获取当前用户是作者的笔记
        sidebar_notes = list(
            Note.objects.filter(author=user)
            .order_by('-updated_at')  # 按更新时间排序更实用
            .values('id', 'title')
        )
        # 缓存结果
        cache.set(sidebar_notes_key, sidebar_notes, timeout=900)  # 缓存15分钟

    initial_data = {
        'sidebar_notes': sidebar_notes,
        'has_notes': bool(sidebar_notes),
        'csrf_token': request.COOKIES.get('csrftoken')
    }
    context = {'initial_data': initial_data}
    return render(request, 'knowledge/knowledge_list.html', context)

