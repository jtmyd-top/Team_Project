"""Moderation common auth helpers."""
from .base import *  # noqa: F401,F403

def _require_admin(request):
    """返回 None 表示放行；否则返回 403 响应。"""
    if not request.user.is_superuser:
        return HttpResponseForbidden('仅超级管理员可访问')
    return None

__all__ = [
    '_require_admin',
]
