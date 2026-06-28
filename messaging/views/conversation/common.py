"""Conversation view shared imports."""
import json
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from notifications.services import notify_user
from .._constants import NEW_CONV_DAILY_LIMIT, RECALL_WINDOW_SECONDS
from .._helpers import (
    _apply_disappearing,
    _attachment_preview,
    _body_string,
    _check_send_permissions,
    _clone_forwarded_attachments,
    _conversation_settings_payload,
    _get_avatar_url,
    _get_settings,
    _is_new_conversation,
    _load_message_attachments,
    _maybe_send_new_message_email,
    _message_payload,
    _parse_message_page,
    _message_preview,
    _message_search_q,
    _message_searchable_text,
    _push_message_read_event,
    _push_message_recalled_event,
    _push_new_message_events,
    _refresh_message_purge_schedule,
    _refresh_purge_schedule_for_messages,
    _server_error_response,
    _slice_latest_page,
    _today_new_conv_count,
    _toggle_field,
    _update_conversation_state,
    _validate_message_content,
    _validate_send_message_input,
    _verify_new_conversation_quota,
    _visible_messages_qs,
)

logger = logging.getLogger(__name__)


__all__ = [name for name in globals() if not name.startswith("__")]
