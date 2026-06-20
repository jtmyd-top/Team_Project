"""Group common users helpers."""
from .base import *  # noqa: F401,F403

def _group_avatar_url(group):
    if getattr(group, 'avatar', None):
        try:
            return group.avatar.url
        except Exception:
            logger.debug('无法获取群头像 URL', exc_info=True)
    return '/static/img/default-avatar.png'

def _user_payload(user):
    if user is None:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'avatar': _get_avatar_url(user),
    }

__all__ = [
    '_group_avatar_url',
    '_user_payload',
]
