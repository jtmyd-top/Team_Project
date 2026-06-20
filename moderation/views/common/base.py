"""Moderation view shared imports and constants."""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_http_methods

from messaging.views._helpers import (
    _get_avatar_url,
    _message_preview,
    _parse_merged_forward,
    _serve_attachment_file,
    _server_error_response,
)
from notifications.services import notify_user

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
CONTEXT_WINDOW = 6  # 关联消息上下文：违规消息前后各取若干条

DURATION_MAP = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    'permanent': None,
}
DURATION_LABEL = {
    '24h': '24 小时',
    '7d': '7 天',
    '30d': '30 天',
    'permanent': '永久',
}

SANCTION_ACTION_PREFIX = {
    'mute_messages': 'mute',
    'ban_comments': 'ban_comments',
    'ban_public_notes': 'ban_public_notes',
    'ban_login': 'ban_login',
}

ALLOWED_SANCTIONS_BY_REPORT_TYPE = {
    'message': {'mute_messages', 'ban_login'},
    'attachment': {'mute_messages', 'ban_login'},
    'note': {'ban_public_notes', 'ban_login'},
    'comment': {'ban_comments', 'ban_login'},
}


__all__ = [
    'json',
    'logging',
    'login_required',
    'User',
    'transaction',
    'Q',
    'Http404',
    'HttpResponseForbidden',
    'JsonResponse',
    'get_object_or_404',
    'redirect',
    'render',
    'strip_tags',
    'timezone',
    'timedelta',
    'require_http_methods',
    '_get_avatar_url',
    '_message_preview',
    '_parse_merged_forward',
    '_serve_attachment_file',
    '_server_error_response',
    'notify_user',
    'logger',
    'PAGE_SIZE',
    'CONTEXT_WINDOW',
    'DURATION_MAP',
    'DURATION_LABEL',
    'SANCTION_ACTION_PREFIX',
    'ALLOWED_SANCTIONS_BY_REPORT_TYPE',
]
