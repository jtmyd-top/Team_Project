"""Vault access and lock service helpers."""

import logging
import secrets
import time
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse

from accounts.services import verify_2fa_for_request
from core.utils.request_utils import get_client_ip


logger = logging.getLogger(__name__)

VAULT_ACCESS_WINDOW = 30 * 60
VAULT_SESSION_ACCESS_WINDOW = 24 * 60 * 60
VAULT_DEVICE_FAIL_THRESHOLD = 3
VAULT_USER_FAIL_THRESHOLD = 5
VAULT_IP_FAIL_THRESHOLD = 10
VAULT_DEVICE_LOCK_SECONDS = 60
VAULT_USER_LOCK_SECONDS = 86400
DEVICE_FAIL_THRESHOLD = 3
IP_FAIL_THRESHOLD = 10
VAULT_CAPTCHA_THRESHOLD = 3
VAULT_ALERT_THRESHOLD = 3


def get_vault_access_key(user_id_or_request):
    if hasattr(user_id_or_request, 'session'):
        request = user_id_or_request
        if not request.session.session_key:
            request.session.create()
        return f'vault_access:{request.session.session_key}'
    return f'vault_access:{user_id_or_request}'


def get_vault_fail_key(user_id_or_request):
    if hasattr(user_id_or_request, 'session'):
        request = user_id_or_request
        if not request.session.session_key:
            request.session.create()
        return f'vault_fail:{request.session.session_key}'
    return f'vault_fail:{user_id_or_request}'


def get_vault_lock_key(user_id_or_request):
    if hasattr(user_id_or_request, 'session'):
        request = user_id_or_request
        if not request.session.session_key:
            request.session.create()
        return f'vault_lock:{request.session.session_key}'
    return f'vault_lock:{user_id_or_request}'


def get_vault_user_fail_key(user_id):
    if hasattr(user_id, 'id'):
        user_id = user_id.id
    return f'vault_user_fail:{user_id}'


def get_vault_user_lock_key(user_id):
    if hasattr(user_id, 'id'):
        user_id = user_id.id
    return f'vault_user_lock:{user_id}'


def get_vault_fail_count(user_id):
    return cache.get(get_vault_fail_key(user_id), 0)


def increment_vault_fail_count(user_id, request=None, device_token=None):
    from accounts.models import AccessLog, TrustedDevice

    actual_user_id = user_id.id if hasattr(user_id, 'id') else user_id
    device_fail_key = get_vault_fail_key(request if request else user_id)
    device_lock_key = get_vault_lock_key(request if request else user_id)

    device_current = cache.get(device_fail_key, 0)
    device_new_count = device_current + 1
    cache.set(device_fail_key, device_new_count, timeout=900)

    device_lock_seconds = 0
    if device_new_count >= VAULT_DEVICE_FAIL_THRESHOLD:
        device_lock_seconds = VAULT_DEVICE_LOCK_SECONDS
        lock_expire_time = int(time.time()) + device_lock_seconds
        cache.set(device_lock_key, lock_expire_time, timeout=device_lock_seconds)

    user_fail_key = get_vault_user_fail_key(actual_user_id)
    user_lock_key = get_vault_user_lock_key(actual_user_id)
    user_current = cache.get(user_fail_key, 0)
    user_new_count = user_current + 1
    cache.set(user_fail_key, user_new_count, timeout=3600)

    user_lock_seconds = 0
    if user_new_count >= VAULT_USER_FAIL_THRESHOLD:
        user_lock_seconds = VAULT_USER_LOCK_SECONDS
        lock_expire_time = int(time.time()) + user_lock_seconds
        cache.set(user_lock_key, lock_expire_time, timeout=user_lock_seconds)

    lock_seconds = max(device_lock_seconds, user_lock_seconds)
    require_captcha = device_new_count >= VAULT_CAPTCHA_THRESHOLD

    if request:
        ip_address = get_client_ip(request)
        if hasattr(user_id, 'username'):
            user_identifier = user_id.username
        elif hasattr(request, 'user') and request.user.is_authenticated:
            user_identifier = request.user.username
        else:
            user_identifier = str(actual_user_id)

        AccessLog.record_vault_fail(
            user_identifier=user_identifier,
            ip_address=ip_address,
            details=f'Device failures: {device_new_count}; user failures: {user_new_count}',
        )

        if device_token:
            device = TrustedDevice.get_by_token(device_token)
            if device:
                device.increment_fail()

        check_and_ban_ip(ip_address, user_identifier)

    return device_new_count, lock_seconds, require_captcha


def check_and_ban_ip(ip_address, user_identifier='anonymous'):
    from accounts.models import AccessLog

    total_fails = AccessLog.get_ip_fail_count(ip_address, hours=24)
    if total_fails >= IP_FAIL_THRESHOLD:
        ban_key = f'banned_ip:{ip_address}'
        if not cache.get(ban_key):
            cache.set(ban_key, {
                'reason': f'Auto-banned after {total_fails} failures in 24 hours.',
                'banned_at': int(time.time()),
                'user': user_identifier,
            }, timeout=86400)

            AccessLog.objects.create(
                user_identifier=user_identifier,
                ip_address=ip_address,
                action='ip_banned',
                details=f'Auto-banned after {total_fails} failures in 24 hours.',
            )


def reset_vault_fail_count(user_id, request=None):
    cache.delete(get_vault_fail_key(request if request else user_id))
    cache.delete(get_vault_lock_key(request if request else user_id))

    actual_user_id = user_id.id if hasattr(user_id, 'id') else user_id
    cache.delete(get_vault_user_fail_key(actual_user_id))
    cache.delete(get_vault_user_lock_key(actual_user_id))


def reset_vault_fail_count_for_user(user_id):
    actual_user_id = user_id.id if hasattr(user_id, 'id') else user_id
    reset_vault_fail_count(actual_user_id)

    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection('default')
        for pattern in ['*vault_fail*', '*vault_lock*']:
            for cache_key in conn.keys(pattern):
                conn.delete(cache_key)
    except Exception:
        pass

    logger.info("Cleared vault lock state for user %s after password reset", actual_user_id)


def on_password_reset(user):
    from accounts.models import AccessLog

    reset_vault_fail_count_for_user(user.id)

    try:
        user_ips = AccessLog.objects.filter(
            user_identifier=user.username,
            action='vault_fail',
        ).values_list('ip_address', flat=True).distinct()

        for ip_address in user_ips:
            if ip_address:
                cache.delete(f'banned_ip:{ip_address}')

        AccessLog.objects.filter(
            user_identifier=user.username,
            action__in=['vault_fail', 'ip_banned'],
        ).delete()

        logger.info(
            "Password reset cleared vault IP restrictions for user %s: %s",
            user.id,
            set(user_ips),
        )
    except Exception as exc:
        logger.error(
            "Password reset cleanup failed for user %s: %s",
            user.id,
            exc,
            exc_info=True,
        )


def check_vault_locked(user_id, request=None):
    actual_user_id = user_id.id if hasattr(user_id, 'id') else user_id
    user_lock_key = get_vault_user_lock_key(actual_user_id)
    user_fail_key = get_vault_user_fail_key(actual_user_id)
    user_lock_expire = cache.get(user_lock_key)
    user_fail_count = cache.get(user_fail_key, 0)

    if user_lock_expire is not None:
        remaining = user_lock_expire - int(time.time())
        if remaining > 0:
            return True, remaining, user_fail_count
        cache.delete(user_lock_key)
        cache.delete(user_fail_key)

    device_lock_key = get_vault_lock_key(request if request else user_id)
    device_fail_key = get_vault_fail_key(request if request else user_id)
    device_lock_expire = cache.get(device_lock_key)
    device_fail_count = cache.get(device_fail_key, 0)

    if device_lock_expire is not None:
        remaining = device_lock_expire - int(time.time())
        if remaining > 0:
            return True, remaining, device_fail_count
        cache.delete(device_lock_key)
        cache.delete(device_fail_key)

    return False, 0, device_fail_count


def send_vault_security_alert(user, fail_count, ip_address=None):
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    alert_key = f'vault_alert_sent:{user.id}'
    if cache.get(alert_key):
        return

    try:
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_info = f' IP: {ip_address}' if ip_address else ''

        send_mail(
            'Vault security alert',
            (
                'We detected repeated failed vault access attempts.\n\n'
                f'Time: {current_time}\n'
                f'Failure count: {fail_count}\n'
                f'{ip_info}\n'
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        cache.set(alert_key, True, timeout=3600)
    except Exception as exc:
        logger.error("Failed to send vault security alert: %s", exc, exc_info=True)


def check_vault_access(request):
    return cache.get(get_vault_access_key(request)) is not None


def grant_vault_access(request, window_seconds=None, session_scoped=False):
    if window_seconds is None:
        window_seconds = VAULT_ACCESS_WINDOW

    cache_key = get_vault_access_key(request)
    expire_time = int(time.time()) + window_seconds
    cache.set(cache_key, {
        'expire_time': expire_time,
        'session_scoped': bool(session_scoped),
    }, timeout=window_seconds)
    return expire_time


def revoke_vault_access(request):
    cache.delete(get_vault_access_key(request))


def get_vault_access_remaining(request):
    cached_access = cache.get(get_vault_access_key(request))
    if cached_access is None:
        return 0
    expire_time = cached_access.get('expire_time') if isinstance(cached_access, dict) else cached_access
    return max(0, expire_time - int(time.time()))


def is_vault_access_session_scoped(request):
    cached_access = cache.get(get_vault_access_key(request))
    return isinstance(cached_access, dict) and bool(cached_access.get('session_scoped'))


def verify_captcha_for_vault(captcha_type, turnstile_token, image_captcha, user_id, request):
    if captcha_type == 'turnstile':
        if not turnstile_token:
            return False, '请完成人机验证'

        from core.utils.turnstile import get_turnstile_verification_detail

        result = get_turnstile_verification_detail(turnstile_token, get_client_ip(request))
        if not result.get('success'):
            return False, result.get('message', '人机验证失败，请重试')
        return True, ''

    if captcha_type == 'image':
        if not image_captcha or len(image_captcha) < 4:
            return False, '请输入图片验证码'

        cache_key = f'vault_image_captcha:{user_id}'
        stored_code = cache.get(cache_key)
        if not stored_code:
            return False, '图片验证码已过期'

        if not secrets.compare_digest(str(stored_code).lower(), str(image_captcha).lower()):
            return False, '图片验证码错误'

        cache.delete(cache_key)
        return True, ''

    return False, '未知的验证码类型'


def verify_vault_2fa(request, code, use_backup=False, captcha_params=None, duration_minutes=None):
    user = request.user
    profile = getattr(user, 'profile', None)

    session_scoped = False
    if duration_minutes is None:
        window_seconds = VAULT_ACCESS_WINDOW
    else:
        if isinstance(duration_minutes, str):
            try:
                duration_minutes = int(duration_minutes)
            except ValueError:
                duration_minutes = 30

        if duration_minutes == 0:
            window_seconds = VAULT_SESSION_ACCESS_WINDOW
            session_scoped = True
        elif duration_minutes < 1:
            window_seconds = VAULT_ACCESS_WINDOW
        elif duration_minutes > 720:
            window_seconds = 720 * 60
        else:
            window_seconds = duration_minutes * 60

    if not profile:
        return {
            'success': False,
            'message': '用户配置不存在',
            'expire_time': 0,
            'status': 'error',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': 0,
            'require_captcha': False,
            'window_seconds': 0,
            'session_scoped': False,
        }

    if not profile.two_fa_enabled:
        expire_time = grant_vault_access(request, window_seconds=window_seconds, session_scoped=session_scoped)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': get_vault_access_remaining(request),
            'require_captcha': False,
            'window_seconds': window_seconds,
            'session_scoped': session_scoped,
        }

    is_locked, lock_remaining, fail_count = check_vault_locked(user.id, request)
    if is_locked:
        return {
            'success': False,
            'message': f'错误次数过多，请等待 {lock_remaining} 秒后重试',
            'expire_time': 0,
            'status': 'locked',
            'fail_count': fail_count,
            'lock_seconds': lock_remaining,
            'remaining_seconds': 0,
            'require_captcha': False,
            'window_seconds': 0,
            'session_scoped': False,
        }

    if fail_count >= VAULT_CAPTCHA_THRESHOLD:
        if not captcha_params:
            return {
                'success': False,
                'message': '请完成人机验证',
                'expire_time': 0,
                'status': 'require_captcha',
                'fail_count': fail_count,
                'lock_seconds': 0,
                'remaining_seconds': 0,
                'require_captcha': True,
                'window_seconds': 0,
                'session_scoped': False,
            }

        captcha_success, captcha_message = verify_captcha_for_vault(
            captcha_params.get('captcha_type', 'turnstile'),
            captcha_params.get('turnstile_token', ''),
            captcha_params.get('image_captcha', ''),
            user.id,
            request,
        )
        if not captcha_success:
            return {
                'success': False,
                'message': captcha_message,
                'expire_time': 0,
                'status': 'require_captcha',
                'fail_count': fail_count,
                'lock_seconds': 0,
                'remaining_seconds': 0,
                'require_captcha': True,
                'window_seconds': 0,
                'session_scoped': False,
            }

    success, message = verify_2fa_for_request(request, code, use_backup)
    if success:
        reset_vault_fail_count(user.id, request)
        expire_time = grant_vault_access(request, window_seconds=window_seconds, session_scoped=session_scoped)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': get_vault_access_remaining(request),
            'require_captcha': False,
            'window_seconds': window_seconds,
            'session_scoped': session_scoped,
        }

    new_fail_count, lock_seconds, require_captcha = increment_vault_fail_count(user.id, request)
    if new_fail_count >= VAULT_ALERT_THRESHOLD:
        send_vault_security_alert(user, new_fail_count, get_client_ip(request))

    if lock_seconds > 0:
        return {
            'success': False,
            'message': f'错误次数过多，请等待 {lock_seconds} 秒后重试',
            'expire_time': 0,
            'status': 'locked',
            'fail_count': new_fail_count,
            'lock_seconds': lock_seconds,
            'remaining_seconds': 0,
            'require_captcha': False,
            'window_seconds': 0,
            'session_scoped': False,
        }

    if require_captcha:
        return {
            'success': False,
            'message': message or '验证码错误',
            'expire_time': 0,
            'status': 'require_captcha',
            'fail_count': new_fail_count,
            'lock_seconds': 0,
            'remaining_seconds': 0,
            'require_captcha': True,
            'window_seconds': 0,
            'session_scoped': False,
        }

    return {
        'success': False,
        'message': message or '验证码错误',
        'expire_time': 0,
        'status': 'error',
        'fail_count': new_fail_count,
        'lock_seconds': 0,
        'remaining_seconds': 0,
        'require_captcha': False,
        'window_seconds': 0,
        'session_scoped': False,
    }


def require_vault_access(view_func):
    @wraps(view_func)
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

        if check_vault_access(request):
            return view_func(request, *args, **kwargs)

        return JsonResponse({
            'status': 'require_vault_2fa',
            'code': 'require_vault_2fa',
            'message': '访问保险柜需要两步验证',
            'method': profile.two_fa_method,
        }, status=200)

    return wrapper
