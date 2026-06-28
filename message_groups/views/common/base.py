"""Group view shared imports and constants."""
import json
import logging
import re
from datetime import datetime, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from moderation.services import message_report_snapshot
from notifications.services import notify_user
from messaging.views._constants import MESSAGE_CONTENT_MAX_LENGTH, RECALL_WINDOW_SECONDS
from messaging.views._helpers import (
    _attachment_payload,
    _attachment_preview,
    _body_string,
    _get_avatar_url,
    _load_message_attachments,
    _maybe_send_group_mention_email,
    _message_searchable_text,
    _normalize_attachment_ids,
    _parse_message_page,
    _server_error_response,
    _slice_latest_page,
)

logger = logging.getLogger(__name__)

MAX_OWNED_MESSAGE_GROUPS = 3
MAX_MESSAGE_GROUP_MEMBERS = 200


def rate_limit(key_prefix, max_requests=10, window_seconds=60):
    """
    速率限制装饰器

    Args:
        key_prefix: 缓存key前缀
        max_requests: 时间窗口内的最大请求次数
        window_seconds: 时间窗口（秒）
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR', 'anonymous')
            cache_key = f'{key_prefix}:{user_id}'

            # 获取当前请求计数
            request_count = cache.get(cache_key, 0)

            if request_count >= max_requests:
                return JsonResponse({
                    'error': f'请求过于频繁，请在{window_seconds}秒后重试',
                    'retry_after': window_seconds
                }, status=429)

            # 增加计数
            cache.set(cache_key, request_count + 1, window_seconds)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator

__all__ = [
    'json',
    'logging',
    're',
    'datetime',
    'timedelta',
    'login_required',
    'User',
    'cache',
    'transaction',
    'F',
    'Q',
    'Http404',
    'JsonResponse',
    'get_object_or_404',
    'timezone',
    'require_http_methods',
    'message_report_snapshot',
    'notify_user',
    'MESSAGE_CONTENT_MAX_LENGTH',
    'RECALL_WINDOW_SECONDS',
    '_attachment_payload',
    '_attachment_preview',
    '_body_string',
    '_get_avatar_url',
    '_load_message_attachments',
    '_maybe_send_group_mention_email',
    '_message_searchable_text',
    '_normalize_attachment_ids',
    '_parse_message_page',
    '_server_error_response',
    '_slice_latest_page',
    'logger',
    'MAX_OWNED_MESSAGE_GROUPS',
    'MAX_MESSAGE_GROUP_MEMBERS',
    'rate_limit',
]
