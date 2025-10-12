# knowledge_project/decorators.py
import time
import hashlib
import pyotp
from functools import wraps
from django.http import JsonResponse


def verify_2fa_for_request(request, code, use_backup=False):
    """
    统一的2FA验证函数

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

    # 1. 备用验证码验证
    if use_backup:
        if not profile.backup_codes:
            return False, '没有可用的备用验证码'

        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in profile.backup_codes:
            # 验证成功，删除已使用的备用码
            profile.backup_codes.remove(code_hash)
            profile.save(update_fields=['backup_codes'])
            return True, ''
        else:
            return False, '备用验证码错误'

    # 2. TOTP验证器验证
    elif profile.two_fa_method == 'totp':
        if not profile.totp_secret:
            return False, '2FA配置错误'

        totp = pyotp.TOTP(profile.totp_secret)
        if totp.verify(code, valid_window=1):
            return True, ''
        else:
            return False, '验证码错误'

    # 3. 邮箱验证码验证
    elif profile.two_fa_method == 'email':
        # 从session获取验证码
        session_code = request.session.get('operation_2fa_email_code')
        session_time = request.session.get('operation_2fa_email_time')

        if not session_code or not session_time:
            return False, '验证码已过期，请重新获取'

        # 检查有效期（5分钟）
        if time.time() - float(session_time) > 300:
            # 清除过期的验证码
            if 'operation_2fa_email_code' in request.session:
                del request.session['operation_2fa_email_code']
            if 'operation_2fa_email_time' in request.session:
                del request.session['operation_2fa_email_time']
            return False, '验证码已过期，请重新获取'

        if session_code == code:
            # 验证成功，清除session
            if 'operation_2fa_email_code' in request.session:
                del request.session['operation_2fa_email_code']
            if 'operation_2fa_email_time' in request.session:
                del request.session['operation_2fa_email_time']
            return True, ''
        else:
            return False, '验证码错误'

    return False, '未知的2FA验证方式'


def require_2fa_verified(view_func):
    """
    装饰器：要求2FA验证才能执行操作

    用法：
        @login_required
        @require_2fa_verified
        def sensitive_operation(request):
            # 执行敏感操作
            pass

    工作流程：
        1. 检查用户是否启用2FA
        2. 如果启用，从请求中获取2FA验证码
        3. 验证通过后执行视图函数
        4. 验证失败返回错误
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        # 检查是否已登录
        if not user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': '请先登录'
            }, status=403)

        profile = getattr(user, 'profile', None)

        # 如果用户未启用2FA，直接执行
        if not profile or not profile.two_fa_enabled:
            return view_func(request, *args, **kwargs)

        # 从请求中获取2FA验证码
        try:
            import json
            data = json.loads(request.body)
            two_fa_code = data.get('two_fa_code', '')
            use_backup = data.get('use_backup', False)
        except (json.JSONDecodeError, AttributeError):
            # 如果无法解析JSON，尝试从POST获取
            two_fa_code = request.POST.get('two_fa_code', '')
            use_backup = request.POST.get('use_backup') == 'true'

        # 如果没有提供验证码，返回需要2FA验证的响应
        if not two_fa_code:
            return JsonResponse({
                'status': 'require_2fa',
                'message': '此操作需要两因素认证验证',
                'method': profile.two_fa_method
            })

        # 验证2FA码
        success, message = verify_2fa_for_request(request, two_fa_code, use_backup)

        if not success:
            return JsonResponse({
                'status': 'error',
                'message': message
            }, status=400)

        # 验证通过，执行视图函数
        return view_func(request, *args, **kwargs)

    return wrapper