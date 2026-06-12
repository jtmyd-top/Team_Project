# knowledge_project/decorators.py
"""
改进版的2FA装饰器
实现了更安全的验证机制和更好的错误处理
"""
import time
import hashlib
import pyotp
import secrets
import json
from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import logging
from knowledge_project.utils.request_utils import get_client_ip as resolve_client_ip

logger = logging.getLogger(__name__)


def get_request_data(request):
    """
    统一获取请求数据（JSON或POST）
    """
    try:
        if request.content_type == 'application/json':
            return json.loads(request.body or b'{}')
        return dict(request.POST)
    except Exception:
        return {}


def get_param(request, key, default=None):
    """
    从请求中获取参数（优先JSON，其次POST）
    """
    data = get_request_data(request)
    value = data.get(key, default)
    # 如果是列表（来自POST），取第一个值
    if isinstance(value, list) and len(value) > 0:
        return value[0]
    return value


def verify_backup_code_secure(profile, code):
    """
    安全地验证并消费备用码
    使用恒定时间比较和原子操作
    """
    if not profile.backup_codes:
        return False

    code_hash = hashlib.sha256(code.encode()).hexdigest()

    with transaction.atomic():
        from knowledge_project.models import Profile
        locked_profile = Profile.objects.select_for_update().get(pk=profile.pk)
        backup_codes = locked_profile.backup_codes or []

        matched_index = -1
        for i, stored_hash in enumerate(backup_codes):
            if secrets.compare_digest(stored_hash, code_hash):
                matched_index = i
                break

        if matched_index >= 0:
            new_codes = backup_codes[:matched_index] + backup_codes[matched_index + 1:]
            locked_profile.backup_codes = new_codes
            locked_profile.save(update_fields=['backup_codes'])
            logger.info("用户 %s 使用了备用验证码，剩余 %s 个", profile.user.id, len(new_codes))
            return True

    return False


def verify_totp_with_replay_protection(profile, code):
    if not profile.totp_secret:
        return False, '2FA配置错误'

    totp = pyotp.TOTP(profile.totp_secret)
    if not totp.verify(code, valid_window=1):
        return False, '验证码错误'

    replay_key = f'totp_used:{profile.user.id}:{code}'
    if cache.get(replay_key):
        logger.warning("用户 %s 尝试重用TOTP验证码", profile.user.id)
        return False, '该验证码已被使用，请等待新的验证码'

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
        logger.warning("用户 %s 2FA验证尝试过多", user.id)
        return False, '验证尝试过多，请5分钟后重试'

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
            message = '未知的2FA验证方式'

        if success:
            cache.delete(attempt_key)
            logger.info("用户 %s 2FA验证成功", user.id)
        else:
            logger.warning("用户 %s 2FA验证失败: %s", user.id, message)

        return success, message
    except Exception as e:
        logger.error("2FA验证异常: %s", e, exc_info=True)
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
                'message': '请先登录'
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
                'message': '此操作需要两因素认证验证',
                'method': profile.two_fa_method
            }, status=200)

        success, message = verify_2fa_for_request(request, code, use_backup)
        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message
            }, status=400)

        return view_func(request, *args, **kwargs)

    return wrapper


def send_operation_2fa_email(user, operation_type='general'):
    import random
    import datetime
    from django.core.mail import send_mail
    from django.conf import settings
    from django.utils import timezone

    cache_key = f'op2fa:{user.id}'
    send_lock_key = f'op2fa_send_lock:{user.id}:{operation_type}'
    if cache.get(send_lock_key):
        logger.info("用户 %s 的 %s 验证码发送过于频繁，已跳过", user.id, operation_type)
        return True, ''

    user_identifier = f"user_{user.id}"
    purpose_hourly_key = f"email_code_hourly_{operation_type}_2fa_{user_identifier}"
    purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)
    if purpose_hourly_attempts >= 3:
        return False, '该操作每小时验证码发送已达上限（3次），请稍后再试。'

    purpose_daily_key = f"email_code_daily_{operation_type}_2fa_{user_identifier}"
    purpose_daily_attempts = cache.get(purpose_daily_key, 0)
    if purpose_daily_attempts >= 5:
        return False, '该操作每天验证码发送已达上限（5次），请明天再试。'

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
        'email_change': '操作验证码（邮箱修改安全验证）',
        'password_change': '操作验证码（密码修改安全验证）',
        'vault_access': '操作验证码（保密柜访问验证）',
        'general': '操作验证码'
    }
    subject = subjects.get(operation_type, '操作验证码')

    try:
        send_mail(
            subject,
            f'您的{subject}是：{code}。5分钟内有效，请勿泄露给他人。',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False
        )
        logger.info("向用户 %s 发送了 %s", user.id, subject)
        return True, ''
    except Exception as e:
        logger.error("发送 %s 失败: %s", subject, e, exc_info=True)
        cache.delete(send_lock_key)
        return False, '验证码发送失败，请稍后重试'


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
    cache_key = get_vault_fail_key(user_id)
    return cache.get(cache_key, 0)


def increment_vault_fail_count(user_id, request=None, device_token=None):
    from .models import AccessLog, TrustedDevice

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
        ip_address = resolve_client_ip(request)
        user_identifier = 'anonymous'
        if hasattr(user_id, 'username'):
            user_identifier = user_id.username
        elif hasattr(request, 'user') and request.user.is_authenticated:
            user_identifier = request.user.username
        else:
            user_identifier = str(actual_user_id)

        AccessLog.record_vault_fail(
            user_identifier=user_identifier,
            ip_address=ip_address,
            details=f'设备失败: {device_new_count}次, 账户总失败: {user_new_count}次'
        )

        if device_token:
            device = TrustedDevice.get_by_token(device_token)
            if device:
                device.increment_fail()

        check_and_ban_ip(ip_address, user_identifier)

    return device_new_count, lock_seconds, require_captcha


def check_and_ban_ip(ip_address, user_identifier='anonymous'):
    from .models import AccessLog

    total_fails = AccessLog.get_ip_fail_count(ip_address, hours=24)
    if total_fails >= IP_FAIL_THRESHOLD:
        ban_key = f'banned_ip:{ip_address}'
        if not cache.get(ban_key):
            cache.set(ban_key, {
                'reason': f'自动封禁: 24小时内{total_fails}次验证失败',
                'banned_at': int(time.time()),
                'user': user_identifier
            }, timeout=86400)

            AccessLog.objects.create(
                user_identifier=user_identifier,
                ip_address=ip_address,
                action='ip_banned',
                details=f'自动封禁: 24小时内累计{total_fails}次验证失败'
            )


def reset_vault_fail_count(user_id, request=None):
    fail_key = get_vault_fail_key(request if request else user_id)
    lock_key = get_vault_lock_key(request if request else user_id)
    cache.delete(fail_key)
    cache.delete(lock_key)

    actual_user_id = user_id.id if hasattr(user_id, 'id') else user_id
    user_fail_key = get_vault_user_fail_key(actual_user_id)
    user_lock_key = get_vault_user_lock_key(actual_user_id)
    cache.delete(user_fail_key)
    cache.delete(user_lock_key)


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
    from django.core.mail import send_mail
    from django.conf import settings
    from django.utils import timezone

    alert_key = f'vault_alert_sent:{user.id}'
    if cache.get(alert_key):
        return

    try:
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_info = f"，来源IP：{ip_address}" if ip_address else ""

        send_mail(
            '【安全警告】保密柜检测到异常登入尝试',
            f'''尊敬的用户：

您的保密柜检测到多次异常登入尝试。

时间：{current_time}
失败次数：{fail_count} 次{ip_info}
''',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )

        cache.set(alert_key, True, timeout=3600)
    except Exception as e:
        logger.error("发送保密柜安全警告邮件失败: %s", e, exc_info=True)


def check_vault_access(request):
    cache_key = get_vault_access_key(request)
    return cache.get(cache_key) is not None


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
    cache_key = get_vault_access_key(request)
    cache.delete(cache_key)


def get_vault_access_remaining(request):
    cache_key = get_vault_access_key(request)
    cached_access = cache.get(cache_key)
    if cached_access is None:
        return 0
    if isinstance(cached_access, dict):
        expire_time = cached_access.get('expire_time')
    else:
        expire_time = cached_access
    remaining = expire_time - int(time.time())
    return max(0, remaining)


def is_vault_access_session_scoped(request):
    cache_key = get_vault_access_key(request)
    cached_access = cache.get(cache_key)
    return isinstance(cached_access, dict) and bool(cached_access.get('session_scoped'))


def verify_captcha_for_vault(captcha_type, turnstile_token, image_captcha, user_id, request):
    if captcha_type == 'turnstile':
        if not turnstile_token:
            return False, '请完成人机验证'

        from .utils.turnstile import get_turnstile_verification_detail
        ip_address = get_client_ip(request)
        result = get_turnstile_verification_detail(turnstile_token, ip_address)
        if not result.get('success'):
            return False, result.get('message', '人机验证失败，请重试')
        return True, ''

    if captcha_type == 'image':
        if not image_captcha or len(image_captcha) < 4:
            return False, '请输入图片验证码'

        cache_key = f'vault_image_captcha:{user_id}'
        stored_code = cache.get(cache_key)
        if not stored_code:
            return False, '图片验证码已过期，请刷新'

        if not secrets.compare_digest(str(stored_code).lower(), str(image_captcha).lower()):
            return False, '图片验证码错误'

        cache.delete(cache_key)
        return True, ''

    return False, '未知的验证码类型'


def verify_vault_2fa(request, code, use_backup=False, captcha_params=None, duration_minutes=None):
    user = request.user
    profile = getattr(user, 'profile', None)

    if duration_minutes is None:
        window_seconds = VAULT_ACCESS_WINDOW
    else:
        if isinstance(duration_minutes, str):
            try:
                duration_minutes = int(duration_minutes)
            except ValueError:
                duration_minutes = 30

        session_scoped = False
        if duration_minutes == 0:
            window_seconds = VAULT_SESSION_ACCESS_WINDOW
            session_scoped = True
        elif duration_minutes < 1:
            window_seconds = VAULT_ACCESS_WINDOW
        elif duration_minutes > 720:
            window_seconds = 720 * 60
        else:
            window_seconds = duration_minutes * 60
            session_scoped = False
    if duration_minutes is None:
        session_scoped = False

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
            'session_scoped': False
        }

    if not profile.two_fa_enabled:
        expire_time = grant_vault_access(request, window_seconds=window_seconds, session_scoped=session_scoped)
        remaining = get_vault_access_remaining(request)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False,
            'window_seconds': window_seconds,
            'session_scoped': session_scoped
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
            'session_scoped': False
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
                'session_scoped': False
            }

        captcha_type = captcha_params.get('captcha_type', 'turnstile')
        turnstile_token = captcha_params.get('turnstile_token', '')
        image_captcha = captcha_params.get('image_captcha', '')

        captcha_success, captcha_message = verify_captcha_for_vault(
            captcha_type, turnstile_token, image_captcha, user.id, request
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
                'session_scoped': False
            }

    success, message = verify_2fa_for_request(request, code, use_backup)
    if success:
        reset_vault_fail_count(user.id, request)
        expire_time = grant_vault_access(request, window_seconds=window_seconds, session_scoped=session_scoped)
        remaining = get_vault_access_remaining(request)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False,
            'window_seconds': window_seconds,
            'session_scoped': session_scoped
        }

    new_fail_count, lock_seconds, require_captcha = increment_vault_fail_count(user.id, request)
    ip_address = get_client_ip(request)
    if new_fail_count >= VAULT_ALERT_THRESHOLD:
        send_vault_security_alert(user, new_fail_count, ip_address)

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
            'session_scoped': False
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
            'session_scoped': False
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
        'session_scoped': False
    }


def get_client_ip(request):
    return resolve_client_ip(request)


def require_vault_access(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'code': 'unauthorized',
                'message': '请先登录'
            }, status=403)

        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.two_fa_enabled:
            return view_func(request, *args, **kwargs)

        if check_vault_access(request):
            return view_func(request, *args, **kwargs)

        return JsonResponse({
            'status': 'require_vault_2fa',
            'code': 'require_vault_2fa',
            'message': '访问保密柜需要两因素认证验证',
            'method': profile.two_fa_method
        }, status=200)

    return wrapper
