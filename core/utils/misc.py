def get_sidebar_cache_key(user_id):
    return f"sidebar_notes_user_{user_id}"


def log_action(user, obj, action_flag, message=''):
    """
    Record a business action as a Django admin LogEntry.
    """
    from django.contrib.admin.models import LogEntry
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
