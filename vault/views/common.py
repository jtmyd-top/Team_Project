"""Vault view shared imports."""
import base64
import json
import logging
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.services import send_operation_2fa_email
from vault.services import (
    check_vault_access,
    get_vault_access_remaining,
    is_vault_access_session_scoped,
    revoke_vault_access,
    verify_vault_2fa,
)
from notes.models import Note

logger = logging.getLogger(__name__)
