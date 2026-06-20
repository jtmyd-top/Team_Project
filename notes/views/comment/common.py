"""Comment view shared imports."""
import json
import logging
import hashlib
import re
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
import requests

from moderation.models import CommentReport, NoteReport, UserSanction
from notes.models import Note, NoteComment
from moderation.services import comment_report_snapshot, note_report_snapshot
from notifications.services import notify_user

logger = logging.getLogger(__name__)

QQ_MUSIC_HOSTS = {'c6.y.qq.com', 'i.y.qq.com', 'y.qq.com'}
