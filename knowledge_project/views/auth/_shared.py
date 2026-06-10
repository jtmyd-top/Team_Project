"""auth 子包共享模块：统一的 import 块、常量、共享 Form 类。"""
from django.contrib.auth import login
from ...utils.turnstile import verify_turnstile_token, get_turnstile_verification_detail, get_site_key, is_turnstile_enabled
from ...utils.code import check_code
from ..captcha import verify_captcha_unified
from django.http import HttpResponse
from io import BytesIO
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.urls import reverse
import hashlib
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.contrib.auth.models import User
from ...models import auto_generate_tags_for_note
from django.core.mail import send_mail
import random
import string
import time
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from django.db.models import Q
from django.db import models
import json
from django.core.paginator import Paginator
from django.core.cache import cache
from ...models import Note, Asset, Tag, ProfileLike, Profile, Folder, NoteComment
from django.shortcuts import render, redirect
from django.contrib import messages
import subprocess
from ...utils.avatars import save_user_avatar
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ...models import Asset
import mimetypes
import os
import uuid
from django.shortcuts import render, get_object_or_404
import logging
from ...utils.misc import get_sidebar_cache_key, log_action
from django.core.files.base import ContentFile
from collections import deque
import math
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.db import transaction
import threading
import pyotp
import psutil
import platform
import qrcode
import base64
from ...decorators import verify_2fa_for_request, require_2fa_verified
from bs4 import BeautifulSoup

USERNAME_REGEX = re.compile(r'^[a-z][a-z0-9_]{5,}$')


def login_with_persistent_session(request, user):
    """Log in and write the configured session lifetime immediately."""
    login(request, user)
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='必填项。')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)


logger = logging.getLogger(__name__)
