"""测试公共工具：禁掉外网头像拉取、提供建用户/登录/JSON 调用的工厂。"""
from __future__ import annotations

import json
from contextlib import contextmanager
import time
from typing import Any, Optional
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client


@contextmanager
def patched_avatar_fetch():
    """fetch_avatar 会在 User.post_save 中触发外网请求，测试里要拦掉。

    同时拦掉 PIL 字体生成（kumo.ttf 路径在某些环境读不到也无所谓）。
    """
    with patch('accounts.avatar.fetch_avatar', lambda *a, **kw: None), \
         patch('accounts.signals.fetch_avatar_async', lambda *a, **kw: None):
        yield


def make_user(
    username: str = 'alice',
    password: str = 'pass-word-123!',
    email: Optional[str] = None,
    *,
    is_staff: bool = False,
    is_superuser: bool = False,
) -> User:
    """创建一个用户。已经包好 fetch_avatar mock。"""
    if email is None:
        email = f'{username}@example.com'
    with patched_avatar_fetch():
        if is_superuser:
            user = User.objects.create_superuser(username=username, email=email, password=password)
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            if is_staff:
                user.is_staff = True
                user.save(update_fields=['is_staff'])
    return user


def login(client: Client, user: User, password: str = 'pass-word-123!') -> None:
    """通过 client.force_login 直接登录（绕过 2FA / captcha 等流程，测业务逻辑用）。

    需要测真实登录流程时，请直接 POST /api/login/ 而不是用这个。
    """
    logged_in = client.login(username=user.username, password=password)
    if not logged_in:  # pragma: no cover
        raise AssertionError(f'failed to login test user {user.username}')
    session = client.session
    now = int(time.time())
    session['auth_started_at'] = now
    session['last_activity_at'] = now
    session.save()


def post_json(client: Client, url: str, payload: Any | None = None, **extra) -> Any:
    body = '' if payload is None else json.dumps(payload)
    return client.post(url, data=body, content_type='application/json', **extra)


def get_json(client: Client, url: str, **extra) -> Any:
    return client.get(url, **extra)


def parse(response) -> dict:
    """反序列化 JsonResponse —— 失败时把状态码和原始内容塞进异常方便排查。"""
    try:
        return json.loads(response.content.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:  # pragma: no cover
        raise AssertionError(
            f'response is not JSON. status={response.status_code} '
            f'content={response.content[:500]!r}'
        ) from exc
