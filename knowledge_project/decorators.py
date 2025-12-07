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
        operation_type: 操作类型 ('email_change', 'password_change', 'general')
    
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
    
    # 【新增】每日发送次数限制（每个操作类型每天最多3次）
    user_identifier = f"user_{user.id}"
    purpose_daily_key = f"email_code_daily_{operation_type}_2fa_{user_identifier}"
    purpose_daily_attempts = cache.get(purpose_daily_key, 0)
    
    if purpose_daily_attempts >= 3:
        logger.warning(f"用户 {user.id} 的{operation_type}验证码今日发送次数已达上限")
        return False, '您今天已达到该操作的验证码发送上限（3次），请明天再试。'
    
    # 生成6位验证码
    code = ''.join(random.choices('0123456789', k=6))

    # 存储到缓存（5分钟有效）
    cache.set(cache_key, code, timeout=300)
    
    # 设置发送锁，90秒内不允许重复发送同类型的验证码
    cache.set(send_lock_key, True, timeout=90)
    
    # 【新增】更新每日发送次数
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
