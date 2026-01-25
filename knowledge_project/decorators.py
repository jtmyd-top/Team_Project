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

    # 计算输入码的哈希
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    # 使用原子操作
    with transaction.atomic():
        # 锁定profile记录
        from knowledge_project.models import Profile
        locked_profile = Profile.objects.select_for_update().get(pk=profile.pk)
        backup_codes = locked_profile.backup_codes or []

        # 恒定时间比较所有备用码
        matched_index = -1
        for i, stored_hash in enumerate(backup_codes):
            if secrets.compare_digest(stored_hash, code_hash):
                matched_index = i
                break

        if matched_index >= 0:
            # 删除已使用的备用码
            new_codes = backup_codes[:matched_index] + backup_codes[matched_index+1:]
            locked_profile.backup_codes = new_codes
            locked_profile.save(update_fields=['backup_codes'])

            # 记录审计日志
            logger.info(f"用户 {profile.user.id} 使用了备用验证码，剩余 {len(new_codes)} 个")
            return True

    return False


def verify_totp_with_replay_protection(profile, code):
    """
    TOTP验证，带重放保护
    """
    if not profile.totp_secret:
        return False, '2FA配置错误'

    totp = pyotp.TOTP(profile.totp_secret)

    # 验证TOTP码是否有效
    if not totp.verify(code, valid_window=1):
        return False, '验证码错误'

    # 检查重放保护 - 使用验证码本身作为key的一部分
    replay_key = f'totp_used:{profile.user.id}:{code}'
    if cache.get(replay_key):
        logger.warning(f"用户 {profile.user.id} 尝试重用TOTP验证码")
        return False, '该验证码已被使用，请等待新的验证码'

    # 标记这个验证码已被使用（设置60秒过期，覆盖两个时间窗口）
    cache.set(replay_key, True, timeout=60)

    return True, ''


def verify_email_code_from_cache(user_id, code):
    """
    从缓存验证邮箱验证码
    """
    cache_key = f'op2fa:{user_id}'
    stored_code = cache.get(cache_key)

    if not stored_code:
        return False, '验证码已过期或不存在'

    # 恒定时间比较
    if secrets.compare_digest(str(stored_code), str(code)):
        # 验证成功后删除验证码（一次性使用）
        cache.delete(cache_key)
        return True, ''

    return False, '验证码错误'


def verify_2fa_for_request(request, code, use_backup=False):
    """
    改进版的统一2FA验证函数

    Args:
        request: HttpRequest对象
        code: 用户输入的验证码
        use_backup: 是否使用备用验证码

    Returns:
        (success: bool, message: str)
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile or not profile.two_fa_enabled:
        # 未启用2FA，直接通过
        return True, ''

    # 记录验证尝试
    attempt_key = f'2fa_attempts:{user.id}'
    attempts = cache.get(attempt_key, 0)

    # 限制尝试次数（5分钟内最多10次）
    if attempts >= 10:
        logger.warning(f"用户 {user.id} 2FA验证尝试过多")
        return False, '验证尝试过多，请5分钟后重试'

    # 增加尝试计数
    cache.set(attempt_key, attempts + 1, timeout=300)

    success = False
    message = '验证失败'  # 默认错误消息

    try:
        # 1. 备用验证码验证
        if use_backup:
            success = verify_backup_code_secure(profile, code)
            if not success:
                message = '备用验证码错误或已使用'

        # 2. TOTP验证器验证
        elif profile.two_fa_method == 'totp':
            success, message = verify_totp_with_replay_protection(profile, code)

        # 3. 邮箱验证码验证
        elif profile.two_fa_method == 'email':
            success, message = verify_email_code_from_cache(user.id, code)

        else:
            message = '未知的2FA验证方式'

        # 验证成功，重置尝试计数
        if success:
            cache.delete(attempt_key)
            logger.info(f"用户 {user.id} 2FA验证成功")
        else:
            logger.warning(f"用户 {user.id} 2FA验证失败: {message}")

        return success, message

    except Exception as e:
        logger.error(f"2FA验证异常: {e}", exc_info=True)
        return False, '验证过程中发生错误'


def require_2fa_verified(view_func):
    """
    改进版的2FA验证装饰器
    """
    @wraps(view_func)
    @require_POST  # 只允许POST请求
    @csrf_protect  # CSRF保护
    def wrapper(request, *args, **kwargs):
        # 检查用户登录
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'code': 'unauthorized',
                'message': '请先登录'
            }, status=403)

        profile = getattr(request.user, 'profile', None)

        # 如果未启用2FA，直接执行视图
        if not profile or not profile.two_fa_enabled:
            return view_func(request, *args, **kwargs)

        # 获取2FA验证码
        code = get_param(request, 'two_fa_code', '')
        use_backup = get_param(request, 'use_backup', False)

        # 如果没有提供验证码，返回需要2FA的提示
        if not code:
            return JsonResponse({
                'status': 'require_2fa',
                'code': 'require_2fa',
                'message': '此操作需要两因素认证验证',
                'method': profile.two_fa_method
            }, status=200)

        # 验证2FA
        success, message = verify_2fa_for_request(request, code, use_backup)

        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message
            }, status=400)

        # 验证成功，执行原视图
        return view_func(request, *args, **kwargs)

    return wrapper


def send_operation_2fa_email(user, operation_type='general'):
    """
    发送操作验证码邮件（带防重复机制和每日限制）

    Args:
        user: 用户对象
        operation_type: 操作类型 ('email_change', 'password_change', 'general', 'vault_access')

    Returns:
        (success: bool, message: str) - 成功返回(True, ''), 失败返回(False, 错误信息)
    """
    import random
    import datetime
    from django.core.mail import send_mail
    from django.conf import settings
    from django.utils import timezone

    cache_key = f'op2fa:{user.id}'
    
    # 【防重复机制】检查是否在90秒内已经发送过验证码
    send_lock_key = f'op2fa_send_lock:{user.id}:{operation_type}'
    if cache.get(send_lock_key):
        logger.info(f"用户 {user.id} 的{operation_type}验证码发送过于频繁，已跳过")
        # 如果已有验证码，返回True表示不需要再发送
        return True, ''
    
    # 【新增】发送次数限制（每个操作类型每小时3次，每天5次）
    user_identifier = f"user_{user.id}"

    # 每小时发送次数限制
    purpose_hourly_key = f"email_code_hourly_{operation_type}_2fa_{user_identifier}"
    purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)

    if purpose_hourly_attempts >= 3:
        logger.warning(f"用户 {user.id} 的{operation_type}验证码每小时发送次数已达上限")
        return False, '该操作每小时验证码发送已达上限（3次），请稍后再试。'

    # 每天发送次数限制
    purpose_daily_key = f"email_code_daily_{operation_type}_2fa_{user_identifier}"
    purpose_daily_attempts = cache.get(purpose_daily_key, 0)

    if purpose_daily_attempts >= 5:
        logger.warning(f"用户 {user.id} 的{operation_type}验证码每日发送次数已达上限")
        return False, '该操作每天验证码发送已达上限（5次），请明天再试。'
    
    # 生成6位验证码
    code = ''.join(random.choices('0123456789', k=6))

    # 存储到缓存（5分钟有效）
    cache.set(cache_key, code, timeout=300)
    
    # 设置发送锁，90秒内不允许重复发送同类型的验证码
    cache.set(send_lock_key, True, timeout=90)
    
    # 【新增】更新发送次数
    # 更新每小时发送次数
    if purpose_hourly_attempts == 0:
        cache.set(purpose_hourly_key, 1, timeout=3600)   # 1小时
    else:
        cache.incr(purpose_hourly_key)

    # 更新每天发送次数
    if purpose_daily_attempts == 0:
        # 第一次发送，设置过期时间为到第二天凌晨
        now = timezone.now()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        seconds_until_tomorrow = int((tomorrow - now).total_seconds())
        cache.set(purpose_daily_key, 1, timeout=seconds_until_tomorrow)
    else:
        cache.incr(purpose_daily_key)

    # 根据操作类型选择邮件标题
    subjects = {
        'email_change': '操作验证码（邮箱修改安全验证）',
        'password_change': '操作验证码（密码修改安全验证）',
        'vault_access': '操作验证码（保密柜访问验证）',
        'general': '操作验证码'
    }
    subject = subjects.get(operation_type, '操作验证码')

    # 发送邮件
    try:
        send_mail(
            subject,
            f'您的{subject}是：{code}。5分钟内有效，请勿泄露给他人。',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False
        )
        logger.info(f"向用户 {user.id} 发送了{subject}，验证码：{code}")
        return True, ''
    except Exception as e:
        logger.error(f"发送{subject}失败: {e}", exc_info=True)
        # 发送失败时删除锁，允许重试
        cache.delete(send_lock_key)
        return False, '验证码发送失败，请稍后重试'


# ==================== 保密柜（Vault）相关函数 ====================

# 保密柜验证时间窗口（秒），默认30分钟
VAULT_ACCESS_WINDOW = 30 * 60

# 保密柜验证失败惩罚配置
VAULT_FAIL_THRESHOLDS = [
    # (失败次数, 锁定秒数)
    (3, 60),       # 第3次失败：锁定1分钟
    (5, 86400),    # 第5次失败：锁定24小时（全域锁定）
    
]

# 需要CAPTCHA的失败次数阈值
VAULT_CAPTCHA_THRESHOLD = 3

# 发送安全警告邮件的失败次数阈值
VAULT_ALERT_THRESHOLD = 3


def get_vault_access_key(user_id):
    """获取保密柜访问状态的缓存key"""
    return f'vault_access:{user_id}'


def get_vault_fail_key(user_id):
    """获取保密柜验证失败计数的缓存key"""
    return f'vault_fail:{user_id}'


def get_vault_lock_key(user_id):
    """获取保密柜锁定状态的缓存key"""
    return f'vault_lock:{user_id}'


def get_vault_fail_count(user_id):
    """
    获取保密柜验证失败次数

    Returns:
        int: 失败次数
    """
    cache_key = get_vault_fail_key(user_id)
    return cache.get(cache_key, 0)


def increment_vault_fail_count(user_id):
    """
    增加保密柜验证失败次数，并根据次数决定是否锁定

    Returns:
        (fail_count: int, lock_seconds: int, require_captcha: bool)
    """
    fail_key = get_vault_fail_key(user_id)
    lock_key = get_vault_lock_key(user_id)

    # 获取当前失败次数
    current_count = cache.get(fail_key, 0)
    new_count = current_count + 1

    # 更新失败次数（15分钟过期）
    cache.set(fail_key, new_count, timeout=900)

    # 检查是否需要锁定
    lock_seconds = 0
    for threshold, seconds in VAULT_FAIL_THRESHOLDS:
        if new_count >= threshold:
            lock_seconds = seconds

    # 如果需要锁定，设置锁定状态
    if lock_seconds > 0:
        lock_expire_time = int(time.time()) + lock_seconds
        cache.set(lock_key, lock_expire_time, timeout=lock_seconds)
        logger.warning(f"用户 {user_id} 保密柜验证失败 {new_count} 次，锁定 {lock_seconds} 秒")

    # 检查是否需要CAPTCHA
    require_captcha = new_count >= VAULT_CAPTCHA_THRESHOLD

    return new_count, lock_seconds, require_captcha


def reset_vault_fail_count(user_id):
    """
    重置保密柜验证失败次数（验证成功后调用）
    """
    fail_key = get_vault_fail_key(user_id)
    lock_key = get_vault_lock_key(user_id)
    cache.delete(fail_key)
    cache.delete(lock_key)
    logger.info(f"用户 {user_id} 保密柜验证成功，重置失败计数")


def check_vault_locked(user_id):
    """
    检查保密柜是否被锁定

    Returns:
        (is_locked: bool, remaining_seconds: int, fail_count: int)
    """
    lock_key = get_vault_lock_key(user_id)
    fail_key = get_vault_fail_key(user_id)

    lock_expire_time = cache.get(lock_key)
    fail_count = cache.get(fail_key, 0)

    if lock_expire_time is None:
        return False, 0, fail_count

    remaining = lock_expire_time - int(time.time())
    if remaining <= 0:
        # 锁定已过期，清除锁定状态
        cache.delete(lock_key)
        return False, 0, fail_count

    return True, remaining, fail_count


def send_vault_security_alert(user, fail_count, ip_address=None):
    """
    发送保密柜安全警告邮件

    Args:
        user: 用户对象
        fail_count: 失败次数
        ip_address: 来源IP地址
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from django.utils import timezone

    # 检查是否已经发送过警告（1小时内只发一次）
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

如果这不是您本人的操作，请立即：
1. 修改您的账户密码
2. 检查您的两因素认证设置
3. 查看账户的登录记录

如果这是您本人的操作，请忽略此邮件。

此邮件由系统自动发送，请勿回复。
''',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True
        )

        # 标记已发送（1小时内不重复发送）
        cache.set(alert_key, True, timeout=3600)
        logger.info(f"向用户 {user.id} 发送了保密柜安全警告邮件")

    except Exception as e:
        logger.error(f"发送保密柜安全警告邮件失败: {e}", exc_info=True)


def check_vault_access(user):
    """
    检查用户是否已通过保密柜2FA验证（在时间窗口内）

    Args:
        user: 用户对象

    Returns:
        bool: True表示已验证且在有效期内，False表示需要重新验证
    """
    cache_key = get_vault_access_key(user.id)
    return cache.get(cache_key) is not None


def grant_vault_access(user, window_seconds=None):
    """
    授予用户保密柜访问权限（设置时间窗口）

    Args:
        user: 用户对象
        window_seconds: 时间窗口（秒），默认使用VAULT_ACCESS_WINDOW

    Returns:
        int: 过期时间戳
    """
    if window_seconds is None:
        window_seconds = VAULT_ACCESS_WINDOW

    cache_key = get_vault_access_key(user.id)
    expire_time = int(time.time()) + window_seconds
    cache.set(cache_key, expire_time, timeout=window_seconds)

    logger.info(f"用户 {user.id} 获得保密柜访问权限，有效期 {window_seconds} 秒")
    return expire_time


def revoke_vault_access(user):
    """
    撤销用户的保密柜访问权限（主动锁定）

    Args:
        user: 用户对象
    """
    cache_key = get_vault_access_key(user.id)
    cache.delete(cache_key)
    logger.info(f"用户 {user.id} 的保密柜访问权限已撤销")


def get_vault_access_remaining(user):
    """
    获取保密柜访问权限剩余时间

    Args:
        user: 用户对象

    Returns:
        int: 剩余秒数，0表示已过期或未验证
    """
    cache_key = get_vault_access_key(user.id)
    expire_time = cache.get(cache_key)

    if expire_time is None:
        return 0

    remaining = expire_time - int(time.time())
    return max(0, remaining)


def verify_captcha_for_vault(captcha_type, turnstile_token, image_captcha, user_id, request):
    """
    验证保密柜的CAPTCHA

    Args:
        captcha_type: 'turnstile' 或 'image'
        turnstile_token: Turnstile token
        image_captcha: 图片验证码
        user_id: 用户ID
        request: HttpRequest对象

    Returns:
        (success: bool, message: str)
    """
    if captcha_type == 'turnstile':
        if not turnstile_token:
            return False, '请完成人机验证'

        # 使用 turnstile 工具验证
        from .utils.turnstile import get_turnstile_verification_detail
        ip_address = get_client_ip(request)
        result = get_turnstile_verification_detail(turnstile_token, ip_address)

        if not result.get('success'):
            return False, result.get('message', '人机验证失败，请重试')

        return True, ''

    elif captcha_type == 'image':
        if not image_captcha or len(image_captcha) < 4:
            return False, '请输入图片验证码'

        # 验证图片验证码
        from .utils.code import check_code
        cache_key = f'vault_image_captcha:{user_id}'
        stored_code = cache.get(cache_key)

        if not stored_code:
            return False, '图片验证码已过期，请刷新'

        if not secrets.compare_digest(str(stored_code).lower(), str(image_captcha).lower()):
            return False, '图片验证码错误'

        # 验证成功后删除
        cache.delete(cache_key)
        return True, ''

    return False, '未知的验证码类型'


def verify_vault_2fa(request, code, use_backup=False, captcha_params=None):
    """
    验证保密柜2FA并授予访问权限（带速率限制和指数退避）

    Args:
        request: HttpRequest对象
        code: 用户输入的验证码
        use_backup: 是否使用备用验证码
        captcha_params: CAPTCHA参数 {'captcha_type': str, 'turnstile_token': str, 'image_captcha': str}

    Returns:
        dict: {
            'success': bool,
            'message': str,
            'expire_time': int,
            'status': str,  # 'success', 'error', 'locked', 'require_captcha'
            'fail_count': int,
            'lock_seconds': int,
            'remaining_seconds': int,
            'require_captcha': bool
        }
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile:
        return {
            'success': False,
            'message': '用户配置不存在',
            'expire_time': 0,
            'status': 'error',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': 0,
            'require_captcha': False
        }

    # 如果用户未启用2FA，直接授予访问权限
    if not profile.two_fa_enabled:
        expire_time = grant_vault_access(user)
        remaining = get_vault_access_remaining(user)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False
        }

    # 检查是否被锁定
    is_locked, lock_remaining, fail_count = check_vault_locked(user.id)
    if is_locked:
        return {
            'success': False,
            'message': f'错误次数过多，请等待 {lock_remaining} 秒后重试',
            'expire_time': 0,
            'status': 'locked',
            'fail_count': fail_count,
            'lock_seconds': lock_remaining,
            'remaining_seconds': 0,
            'require_captcha': False
        }

    # 检查是否需要CAPTCHA验证（失败次数 >= 3）
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
                'require_captcha': True
            }

        # 验证CAPTCHA
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
                'require_captcha': True
            }

    # 验证2FA
    success, message = verify_2fa_for_request(request, code, use_backup)

    if success:
        # 验证成功，重置失败计数并授予访问权限
        reset_vault_fail_count(user.id)
        expire_time = grant_vault_access(user)
        remaining = get_vault_access_remaining(user)
        return {
            'success': True,
            'message': '',
            'expire_time': expire_time,
            'status': 'success',
            'fail_count': 0,
            'lock_seconds': 0,
            'remaining_seconds': remaining,
            'require_captcha': False
        }

    # 验证失败，增加失败计数
    new_fail_count, lock_seconds, require_captcha = increment_vault_fail_count(user.id)

    # 获取客户端IP
    ip_address = get_client_ip(request)

    # 如果达到警告阈值，发送安全警告邮件
    if new_fail_count >= VAULT_ALERT_THRESHOLD:
        send_vault_security_alert(user, new_fail_count, ip_address)

    # 根据情况返回不同状态
    if lock_seconds > 0:
        return {
            'success': False,
            'message': f'错误次数过多，请等待 {lock_seconds} 秒后重试',
            'expire_time': 0,
            'status': 'locked',
            'fail_count': new_fail_count,
            'lock_seconds': lock_seconds,
            'remaining_seconds': 0,
            'require_captcha': False
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
            'require_captcha': True
        }

    return {
        'success': False,
        'message': message or '验证码错误',
        'expire_time': 0,
        'status': 'error',
        'fail_count': new_fail_count,
        'lock_seconds': 0,
        'remaining_seconds': 0,
        'require_captcha': False
    }


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def require_vault_access(view_func):
    """
    保密柜访问装饰器
    检查用户是否已通过保密柜2FA验证
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'code': 'unauthorized',
                'message': '请先登录'
            }, status=403)

        profile = getattr(request.user, 'profile', None)

        # 如果用户未启用2FA，直接允许访问
        if not profile or not profile.two_fa_enabled:
            return view_func(request, *args, **kwargs)

        # 检查是否在有效期内
        if check_vault_access(request.user):
            return view_func(request, *args, **kwargs)

        # 需要2FA验证
        return JsonResponse({
            'status': 'require_vault_2fa',
            'code': 'require_vault_2fa',
            'message': '访问保密柜需要两因素认证验证',
            'method': profile.two_fa_method
        }, status=200)

    return wrapper
