"""Group view shared imports and constants."""
import json
import logging
import re
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from moderation.services import message_report_snapshot
from notifications.services import notify_user
from messaging.views._constants import MESSAGE_CONTENT_MAX_LENGTH, RECALL_WINDOW_SECONDS
from messaging.views._helpers import (
    _attachment_payload,
    _body_string,
    _get_avatar_url,
    _load_message_attachments,
    _maybe_send_group_mention_email,
    _message_searchable_text,
    _normalize_attachment_ids,
    _server_error_response,
)

logger = logging.getLogger(__name__)

MAX_OWNED_MESSAGE_GROUPS = 3
MAX_MESSAGE_GROUP_MEMBERS = 200

__all__ = [
    'json',
    'logging',
    're',
    'datetime',
    'timedelta',
    'login_required',
    'User',
    'transaction',
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
    '_body_string',
    '_get_avatar_url',
    '_load_message_attachments',
    '_maybe_send_group_mention_email',
    '_message_searchable_text',
    '_normalize_attachment_ids',
    '_server_error_response',
    'logger',
    'MAX_OWNED_MESSAGE_GROUPS',
    'MAX_MESSAGE_GROUP_MEMBERS',
]
