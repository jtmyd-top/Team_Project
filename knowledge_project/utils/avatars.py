"""Compatibility exports for migrated avatar helpers."""

from accounts.avatar import (
    fetch_avatar,
    fetch_avatar_async,
    generate_initial_avatar,
    get_gravatar_url,
    get_qq_avatar_url,
    save_user_avatar,
)

__all__ = [
    'fetch_avatar',
    'fetch_avatar_async',
    'generate_initial_avatar',
    'get_gravatar_url',
    'get_qq_avatar_url',
    'save_user_avatar',
]
