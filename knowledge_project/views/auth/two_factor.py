"""两因素认证 (2FA) 相关端点：启用/禁用/验证/备用码。"""
from ._shared import *
from .login import (
    CustomLoginView,
    LOGIN_2FA_EMAIL_CODE_SESSION_KEY,
    _login_2fa_email_cache_key,
    store_login_2fa_email_code,
)


# ==================== 账户安全功能 API ====================

@login_required
@require_http_methods(["POST"])
def send_operation_2fa_code(request):
    """
    为敏感操作发送2FA验证码 (已修复)
    - TOTP用户：不需要发送邮件，直接使用验证器应用
    - Email用户：发送6位验证码到当前邮箱（5分钟有效期），使用缓存存储
    """
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile or not profile.two_fa_enabled:
        return JsonResponse({
            'status': 'success',
            'message': '未启用两因素认证，无需验证',
            'requires_2fa': False
        })

    if profile.two_fa_method == 'totp':
        return JsonResponse({
            'status': 'success',
            'message': '请使用验证器应用生成验证码',
            'requires_2fa': True,
            'method': 'totp'
        })

    elif profile.two_fa_method == 'email':
        # 使用 decorators.py 中的辅助函数，它会正确地使用缓存
        from ...decorators import send_operation_2fa_email
        success, message = send_operation_2fa_email(user, operation_type='general')
        if success:
            return JsonResponse({
                'status': 'success',
                'message': '验证码已发送至您的邮箱',
                'requires_2fa': True,
                'method': 'email'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': message or '发送验证码失败，请稍后重试'
            }, status=429)

    return JsonResponse({
        'status': 'error',
        'message': '未知的2FA验证方式'
    }, status=400)


@login_required
@require_http_methods(["POST"])
@transaction.atomic  # 添加事务装饰器
def enable_2fa(request):
    """
    启用两因素认证
    - TOTP方式：生成密钥和二维码
    - Email方式：直接启用邮箱验证
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    method = data.get("method", "totp")  # 'totp' 或 'email'

    # 确保profile存在
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        # 如果profile不存在，创建一个
        profile = Profile.objects.create(user=request.user)
        logger.info(f"Created profile for user {request.user.id}")

    # 如果已经启用2FA，不允许重复启用
    if profile.two_fa_enabled:
        return JsonResponse({"status": "error", "message": "两因素认证已启用"}, status=400)

    if method == "totp":
        # 生成 TOTP 密钥
        secret = pyotp.random_base32()

        # 生成 QR 码 URI
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=request.user.email,
            issuer_name="知识管理系统"
        )

        # 生成 QR 码图片
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        # 临时保存密钥到 session，等待验证后再写入数据库
        request.session['temp_totp_secret'] = secret
        request.session['temp_2fa_method'] = 'totp'

        return JsonResponse({
            "status": "success",
            "message": "请扫描二维码并输入验证码",
            "qr_code": f"data:image/png;base64,{qr_code_base64}",
            "secret": secret,  # 也返回密钥文本，方便手动输入
            "requires_verification": True
        })

    elif method == "email":
        # 邮箱验证方式，直接启用，并生成备用码
        profile.two_fa_enabled = True
        profile.two_fa_method = 'email'

        # 生成备用码
        backup_codes = generate_backup_codes_list()
        profile.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]

        profile.save(update_fields=['two_fa_enabled', 'two_fa_method', 'backup_codes'])

        # 添加日志记录
        logger.info(f"Email 2FA enabled for user {request.user.id} with backup codes.")

        return JsonResponse({
            "status": "success",
            "message": "邮箱两因素认证已启用",
            "two_fa_enabled": profile.two_fa_enabled,
            "two_fa_method": profile.two_fa_method,
            "backup_codes": backup_codes,  # 返回明文备用码供用户保存
            "requires_verification": False,
            "rate_limit_warning": {
                "title": "重要提醒：验证码发送频率限制",
                "message": "为了保护您的账户安全，登录验证码每小时最多发送3次，每天最多发送5次。建议妥善保管以下备用验证码，以便在需要时使用。",
                "details": [
                    "登录时每小时最多可发送3次验证码",
                    "登录时每天最多可发送5次验证码",
                    "超过小时限制需等待1小时后重置",
                    "超过天限制需等到第二天凌晨重置",
                    "请务必保存下方的备用验证码",
                    "每个备用码仅可使用一次",
                    "丢失备用码可在设置中重新生成"
                ]
            }
        })

    else:
        return JsonResponse({"status": "error", "message": "不支持的验证方式"}, status=400)


@login_required
@require_http_methods(["POST"])
def verify_2fa_setup(request):
    """
    验证并完成 2FA 设置
    - 对于 TOTP：验证用户输入的验证码是否正确
    - 验证成功后，正式启用 2FA
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    code = data.get("code", "").strip()
    profile = request.user.profile

    # 检查是否有待验证的2FA设置
    temp_method = request.session.get('temp_2fa_method')
    if not temp_method:
        return JsonResponse({"status": "error", "message": "未找到待验证的2FA设置"}, status=400)

    if temp_method == "totp":
        # 从 session 获取临时密钥
        temp_secret = request.session.get('temp_totp_secret')
        if not temp_secret:
            return JsonResponse({"status": "error", "message": "密钥已过期，请重新设置"}, status=400)

        # 验证 TOTP 码
        totp = pyotp.TOTP(temp_secret)
        if not totp.verify(code, valid_window=1):  # valid_window=1 允许前后30秒的时间差
            return JsonResponse({"status": "error", "message": "验证码错误"}, status=400)

        # 验证成功，保存密钥并启用2FA
        profile.totp_secret = temp_secret
        profile.two_fa_method = 'totp'
        profile.two_fa_enabled = True

        # 生成备用码
        backup_codes = generate_backup_codes_list()
        profile.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]

        profile.save(update_fields=['totp_secret', 'two_fa_method', 'two_fa_enabled', 'backup_codes'])

        # 清除 session 中的临时数据
        if 'temp_totp_secret' in request.session:
            del request.session['temp_totp_secret']
        if 'temp_2fa_method' in request.session:
            del request.session['temp_2fa_method']

        return JsonResponse({
            "status": "success",
            "message": "TOTP 两因素认证已成功启用",
            "backup_codes": backup_codes  # 返回明文备用码供用户保存
        })

    elif temp_method == "email":
        # 邮箱方式直接启用
        profile.two_fa_method = 'email'
        profile.two_fa_enabled = True
        profile.save(update_fields=['two_fa_method', 'two_fa_enabled'])

        # 清除 session
        if 'temp_2fa_method' in request.session:
            del request.session['temp_2fa_method']

        return JsonResponse({
            "status": "success",
            "message": "邮箱两因素认证已成功启用"
        })

    return JsonResponse({"status": "error", "message": "未知错误"}, status=500)


@login_required
@require_http_methods(["POST"])
def disable_2fa(request):
    """
    禁用两因素认证
    需要验证当前密码和当前 2FA 凭证
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    password = data.get("password", "")
    code = data.get("code", "").strip()
    use_backup = data.get("use_backup", False)
    profile = request.user.profile

    if not profile.two_fa_enabled:
        return JsonResponse({"status": "error", "message": "未启用两因素认证"}, status=400)

    # 验证密码
    if not request.user.check_password(password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    if not code:
        return JsonResponse({"status": "error", "message": "请输入当前 2FA 验证码或备用码"}, status=400)

    success, message = verify_2fa_for_request(request, code, use_backup)
    if not success:
        return JsonResponse({"status": "error", "message": message}, status=400)

    # 禁用2FA并清除相关数据
    profile.two_fa_enabled = False
    profile.totp_secret = ""
    profile.backup_codes = []
    profile.save(update_fields=['two_fa_enabled', 'totp_secret', 'backup_codes'])

    return JsonResponse({
        "status": "success",
        "message": "两因素认证已禁用"
    })


@login_required
@require_http_methods(["POST"])
def regenerate_backup_codes(request):
    """
    重新生成备用验证码
    需要验证当前密码或2FA验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    password = data.get("password", "")
    profile = request.user.profile

    # 必须已启用2FA
    if not profile.two_fa_enabled:
        return JsonResponse({"status": "error", "message": "未启用两因素认证"}, status=400)

    # 验证密码
    if not request.user.check_password(password):
        return JsonResponse({"status": "error", "message": "密码错误"}, status=400)

    # 生成新的备用码
    backup_codes = generate_backup_codes_list()
    profile.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]
    profile.save(update_fields=['backup_codes'])

    return JsonResponse({
        "status": "success",
        "message": "备用验证码已重新生成",
        "backup_codes": backup_codes
    })


def generate_backup_codes_list():
    """
    生成5个8位数字+字母的备用验证码
    """
    codes = []
    for _ in range(5):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        codes.append(code)
    return codes


# ==================== 两因素认证登录验证 API ====================

@require_http_methods(["POST"])
def verify_2fa_login(request):
    """
    验证2FA登录码
    支持三种验证方式：
    1. TOTP验证器码
    2. 邮箱验证码
    3. 备用验证码
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON格式错误'}, status=400)

    code = data.get('code', '').strip()
    use_backup = data.get('use_backup', False)  # 是否使用备用码
    trust_device = data.get('trust_device', False)  # 是否信任此设备

    # 从session获取待验证的用户ID
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        return JsonResponse({'error': '会话已过期，请重新登录'}, status=400)

    # 检查 2FA 失败次数
    attempt_key = f'login_2fa_attempts:{pending_user_id}'
    attempts = cache.get(attempt_key, 0)
    if attempts >= 5:
        # 清除 2FA session
        request.session.pop('pending_2fa_user_id', None)
        request.session.pop('pending_2fa_method', None)
        return JsonResponse({'error': '验证码错误次数过多，请5分钟后重新登录'}, status=429)

    try:
        user = User.objects.get(id=pending_user_id)
        profile = user.profile
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=400)

    # 验证2FA码
    if use_backup:
        # 使用备用验证码
        if not profile.backup_codes:
            return JsonResponse({'status': 'error', 'message': '没有可用的备用验证码'}, status=400)

        # 检查备用码是否匹配
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in profile.backup_codes:
            # 备用码验证成功，删除已使用的备用码
            profile.backup_codes.remove(code_hash)
            profile.save(update_fields=['backup_codes'])
        else:
            cache.set(attempt_key, attempts + 1, timeout=300)
            return JsonResponse({'error': '备用验证码错误'}, status=400)

    elif profile.two_fa_method == 'totp':
        # TOTP验证器
        if not profile.totp_secret:
            return JsonResponse({'error': '2FA配置错误'}, status=400)

        totp = pyotp.TOTP(profile.totp_secret)
        if not totp.verify(code, valid_window=1):
            cache.set(attempt_key, attempts + 1, timeout=300)
            return JsonResponse({'error': '验证码错误'}, status=400)

    elif profile.two_fa_method == 'email':
        # 邮箱验证码
        session_timestamp = request.session.get('2fa_email_timestamp')

        if not request.session.get(LOGIN_2FA_EMAIL_CODE_SESSION_KEY) or not session_timestamp:
            return JsonResponse({'error': '验证码已过期'}, status=400)

        # 检查有效期（5分钟）
        if time.time() - float(session_timestamp) > 300:
            return JsonResponse({'error': '验证码已过期'}, status=400)

        cached_code_hash = None
        if request.session.session_key:
            cached_code_hash = cache.get(_login_2fa_email_cache_key(request.session.session_key))
        if not cached_code_hash:
            return JsonResponse({'error': '验证码已过期'}, status=400)

        if hashlib.sha256(code.encode()).hexdigest() != cached_code_hash:
            cache.set(attempt_key, attempts + 1, timeout=300)
            return JsonResponse({'error': '验证码错误'}, status=400)

        # 清除已使用的邮箱验证码
        if request.session.session_key:
            cache.delete(_login_2fa_email_cache_key(request.session.session_key))
        if LOGIN_2FA_EMAIL_CODE_SESSION_KEY in request.session:
            del request.session[LOGIN_2FA_EMAIL_CODE_SESSION_KEY]
        if '2fa_email_timestamp' in request.session:
            del request.session['2fa_email_timestamp']

    # 2FA验证成功，清除失败计数
    cache.delete(attempt_key)

    # 2FA验证成功，构建登录方式描述
    login_method_detail = "两因素认证 (验证码)"
    if use_backup:
        # 备用码脱敏处理：显示前3位和后3位
        masked_code = f"{code[:3]}***{code[-3:]}" if len(code) > 6 else f"{code[:3]}***"
        login_method_detail = f"两因素认证 (备用码: {masked_code}，该备用码已失效)"


    # 2FA验证成功，完成登录
    login(request, user)

    # 发送登录通知（使用CustomLoginView的静态方法）
    CustomLoginView().send_login_notification(request, user, login_method=login_method_detail)

    # 清除session中的临时数据
    if 'pending_2fa_user_id' in request.session:
        del request.session['pending_2fa_user_id']
    if 'pending_2fa_method' in request.session:
        del request.session['pending_2fa_method']

    # 构建响应
    response_data = {
        'success': True,
        'message': '登录成功',
        'require_2fa': False
    }

    # 处理信任设备请求
    if trust_device and not use_backup:  # 使用备用码时不允许创建信任设备
        from ...models import TrustedDevice
        device = TrustedDevice.create_device(user, request)
        response = JsonResponse(response_data)
        response.set_cookie(
            'trust_device_token',
            device.device_token,
            max_age=30 * 24 * 3600,  # 30天
            httponly=True,
            samesite='Lax',
            secure=request.is_secure()
        )
        return response

    return JsonResponse(response_data)


@require_http_methods(["POST"])
def resend_2fa_email(request):
    """
    重新发送2FA邮箱验证码（带频率限制）
    """
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        return JsonResponse({'status': 'error', 'message': '会话已过期'}, status=400)

    try:
        user = User.objects.get(id=pending_user_id)
        profile = user.profile
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=400)

    if profile.two_fa_method != 'email':
        return JsonResponse({'status': 'error', 'message': '当前不是邮箱验证方式'}, status=400)

    # 检查登录2FA邮件的发送次数限制
    user_identifier = f"user_{user.id}"

    # 每小时发送次数限制（登录2FA每小时最多3次）
    purpose_hourly_key = f"email_code_hourly_login_2fa_{user_identifier}"
    purpose_hourly_attempts = cache.get(purpose_hourly_key, 0)

    if purpose_hourly_attempts >= 3:
        return JsonResponse({
            'status': 'error',
            'message': '登录验证码每小时发送已达上限（3次），请稍后再试。'
        }, status=429)

    # 每天发送次数限制（登录2FA每天最多5次）
    purpose_daily_key = f"email_code_daily_login_2fa_{user_identifier}"
    purpose_daily_attempts = cache.get(purpose_daily_key, 0)

    if purpose_daily_attempts >= 5:
        return JsonResponse({
            'status': 'error',
            'message': '登录验证码每天发送已达上限（5次），请明天再试。'
        }, status=429)

    # 生成并发送新的验证码
    email_code = ''.join(random.choices(string.digits, k=6))
    store_login_2fa_email_code(request, email_code)

    try:
        send_mail(
            '登录验证码',
            f'您的登录验证码是：{email_code}。5分钟内有效。',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        # 发送成功后，更新计数
        # 更新每小时发送次数
        if purpose_hourly_attempts == 0:
            cache.set(purpose_hourly_key, 1, timeout=3600)   # 1小时
        else:
            cache.incr(purpose_hourly_key)

        # 更新每天发送次数
        if purpose_daily_attempts == 0:
            import datetime
            now = timezone.now()
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            seconds_until_tomorrow = int((tomorrow - now).total_seconds())
            cache.set(purpose_daily_key, 1, timeout=seconds_until_tomorrow)
        else:
            cache.incr(purpose_daily_key)

        return JsonResponse({'status': 'success', 'message': '验证码已重新发送'})
    except Exception as e:
        logger.error(f"重新发送2FA邮件失败: {e}")
        return JsonResponse({'status': 'error', 'message': '发送失败，请稍后重试'}, status=500)
