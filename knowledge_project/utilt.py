def get_sidebar_cache_key(user_id):
    """生成侧边栏笔记列表的缓存键"""
    return f"sidebar_notes_user_{user_id}"
