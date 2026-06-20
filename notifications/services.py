from notifications.models import UserNotification


def notify_user(user, kind, title, body='', **data):
    if user is None or not getattr(user, 'id', None):
        return None

    return UserNotification.objects.create(
        user=user,
        kind=kind,
        title=title[:120],
        body=(body or '')[:2000],
        data=data or {},
    )
