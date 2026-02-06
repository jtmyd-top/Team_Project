def get_sidebar_cache_key(user_id):
    """生成侧边栏笔记列表的缓存键"""
    return f"sidebar_notes_user_{user_id}"


def log_action(user, obj, action_flag, message=''):
    """
    记录业务操作到 Django LogEntry，供战情室审计日志使用。

    参数:
        user: 执行操作的用户
        obj: 被操作的模型实例（Note/Folder 等）
        action_flag: 1=新增, 2=修改, 3=删除
        message: 操作描述（如 "移入回收站"、"永久删除，含 3 篇笔记"）
    """
    from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(obj)
    LogEntry.objects.create(
        user_id=user.pk,
        content_type_id=ct.pk,
        object_id=str(obj.pk),
        object_repr=str(obj)[:200],
        action_flag=action_flag,
        change_message=message,
    )
