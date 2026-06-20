"""Account security and 2FA service helpers."""

import datetime
import hashlib
import json
import logging
import random
import secrets
from functools import wraps

import pyotp
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


logger = logging.getLogger(__name__)


def get_request_data(request):
    try:
        if request.content_type == 'application/json':
            return json.loads(request.body or b'{}')
        return dict(request.POST)
    except Exception:
        return {}


def get_param(request, key, default=None):
    data = get_request_data(request)
    value = data.get(key, default)
    if isinstance(value, list) and len(value) > 0:
        return value[0]
    return value


def verify_backup_code_secure(profile, code):
    if not profile.backup_codes:
        return False

    code_hash = hashlib.sha256(code.encode()).hexdigest()

    with transaction.atomic():
        from accounts.models import Profile

        locked_profile = Profile.objects.select_for_update().get(pk=profile.pk)
        backup_codes = locked_profile.backup_codes or []

        matched_index = -1
        for index, stored_hash in enumerate(backup_codes):
            if secrets.compare_digest(stored_hash, code_hash):
                matched_index = index
                break

        if matched_index >= 0:
            new_codes = backup_codes[:matched_index] + backup_codes[matched_index + 1:]
            locked_profile.backup_codes = new_codes
            locked_profile.save(update_fields=['backup_codes'])
            logger.info("Backup code consumed for user %s; %s codes remain", profile.user.id, len(new_codes))
            return True

    return False


def verify_totp_with_replay_protection(profile, code):
    if not profile.totp_secret:
        return False, '2FA 配置错误'

    totp = pyotp.TOTP(profile.totp_secret)
    if not totp.verify(code, valid_window=1):
        return False, '验证码错误'

    replay_key = f'totp_used:{profile.user.id}:{code}'
    if cache.get(replay_key):
        logger.warning("Rejected reused TOTP code for user %s", profile.user.id)
        return False, '该验证码已被使用'

    cache.set(replay_key, True, timeout=60)
    return True, ''


def verify_email_code_from_cache(user_id, code):
    cache_key = f'op2fa:{user_id}'
    stored_code = cache.get(cache_key)

    if not stored_code:
        return False, '验证码已过期或不存在'

    if secrets.compare_digest(str(stored_code), str(code)):
        cache.delete(cache_key)
        return True, ''

    return False, '验证码错误'


def verify_2fa_for_request(request, code, use_backup=False):
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile or not profile.two_fa_enabled:
        return True, ''

    attempt_key = f'2fa_attempts:{user.id}'
    attempts = cache.get(attempt_key, 0)

    if attempts >= 10:
        logger.warning("Too many 2FA attempts for user %s", user.id)
        return False, '验证尝试过多，请稍后重试'

    cache.set(attempt_key, attempts + 1, timeout=300)

    success = False
    message = '验证失败'

    try:
        if use_backup:
            success = verify_backup_code_secure(profile, code)
            if not success:
                message = '备用验证码错误或已使用'
        elif profile.two_fa_method == 'totp':
            success, message = verify_totp_with_replay_protection(profile, code)
        elif profile.two_fa_method == 'email':
            success, message = verify_email_code_from_cache(user.id, code)
        else:
            message = '未知的 2FA 验证方式'

        if success:
            cache.delete(attempt_key)
            logger.info("2FA verification succeeded for user %s", user.id)
        else:
            logger.warning("2FA verification failed for user %s: %s", user.id, message)

        return success, message
    except Exception as exc:
        logger.error("2FA verification error: %s", exc, exc_info=True)
        return False, '验证过程中发生错误'


def require_2fa_verified(view_func):
    @wraps(view_func)
    @require_POST
    @csrf_protect
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'code': 'unauthorized',
                'message': '请先登录',
            }, status=403)

        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.two_fa_enabled:
            return view_func(request, *args, **kwargs)

        code = get_param(request, 'two_fa_code', '')
        use_backup = get_param(request, 'use_backup', False)

        if not code:
            return JsonResponse({
                'status': 'require_2fa',
                'code': 'require_2fa',
                'message': '此操作需要两步验证',
                'method': profile.two_fa_method,
            }, status=200)

        success, message = verify_2fa_for_request(request, code, use_backup)
        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message,
            }, status=400)

        return view_func(request, *args, **kwargs)

    return wrapper


def send_operation_2fa_email(user, operation_type='general'):
    cache_key = f'op2fa:{user.id}'
    send_lock_key = f'op2fa_send_lock:{user.id}:{operation_type}'
    if cache.get(send_lock_key):
        logger.info("Skipped duplicate 2FA email send for user %s op %s", user.id, operation_type)
        return True, ''

    user_identifier = f'user_{user.id}'
    purpose_hourly_key = f'email_code_hourly_{operation_type}_2fa_{user_identifier}'
    purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)
    if purpose_hourly_attempts >= 3:
        return False, '该操作验证码发送已达上限'

    purpose_daily_key = f'email_code_daily_{operation_type}_2fa_{user_identifier}'
    purpose_daily_attempts = cache.get(purpose_daily_key, 0)
    if purpose_daily_attempts >= 5:
        return False, '该操作验证码发送已达上限'

    code = ''.join(random.choices('0123456789', k=6))
    cache.set(cache_key, code, timeout=300)
    cache.set(send_lock_key, True, timeout=90)

    if purpose_hourly_attempts == 0:
        cache.set(purpose_hourly_key, 1, timeout=3600)
    else:
        cache.incr(purpose_hourly_key)

    if purpose_daily_attempts == 0:
        now = timezone.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        seconds_until_tomorrow = int((tomorrow - now).total_seconds())
        cache.set(purpose_daily_key, 1, timeout=seconds_until_tomorrow)
    else:
        cache.incr(purpose_daily_key)

    subjects = {
        'email_change': 'Email change verification code',
        'password_change': 'Password change verification code',
        'vault_access': 'Vault access verification code',
        'general': 'Verification code',
    }
    subject = subjects.get(operation_type, 'Verification code')

    try:
        send_mail(
            subject,
            f'您的{subject}是：{code}。5分钟内有效。',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info("Sent 2FA email to user %s with subject %s", user.id, subject)
        return True, ''
    except Exception as exc:
        logger.error("Failed to send 2FA email %s: %s", subject, exc, exc_info=True)
        cache.delete(send_lock_key)
        return False, '验证码发送失败'
