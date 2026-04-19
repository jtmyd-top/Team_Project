"""邮箱验证码 / 用户名与邮箱可用性检查。"""
from ._shared import *


def _check_email_availability(request, email: str, *, exclude_self: bool = False):
    """
    统一的邮箱可用性检查逻辑（供多个视图共用）
    - 返回 dict: {'ok': True/False, 'reason': 'invalid'/'taken'/'ok', 'message': str}
    - exclude_self=True 时，会排除当前登录用户（用于“修改邮箱”场景）
    """
    email = (email or "").strip()
    if not email:
        return {'ok': False, 'reason': 'invalid', 'message': '邮箱不能为空'}

    try:
        validate_email(email)
    except ValidationError:
        return {'ok': False, 'reason': 'invalid', 'message': '邮箱格式不正确'}

    qs = User.objects.filter(email__iexact=email)
    # if exclude_self and request.user.is_authenticated:
    #     qs = qs.exclude(pk=request.user.pk)

    if qs.exists():
        return {'ok': False, 'reason': 'taken', 'message': '该邮箱已被绑定'}
    return {'ok': True, 'reason': 'ok', 'message': ''}


class SendEmailCodeView(View):
    """
    发送邮箱验证码
    兼容三种业务：
    - 注册: purpose='register'（默认）
    - 修改邮箱: purpose='email_change'
    - 修改密码: purpose='password_change'

    支持两种模式：
    1. Turnstile模式：需要 turnstile_token 参数进行Turnstile验证码验证
    2. 预验证模式：通过 captcha_pre_validated=true 跳过验证码验证

    安全优化：
    - 使用原子操作限流，避免竞态条件
    - 优化执行顺序，先校验Turnstile验证码再检查限流
    - 使用真实IP地址获取，支持代理环境
    """

    def post(self, request, *args, **kwargs):
        # 1) 解析参数
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '请求格式错误'}, status=400)

        email = (data.get('email') or '').strip()
        turnstile_token = (data.get('turnstile_token') or '').strip()
        image_captcha = (data.get('image_captcha') or '').strip()
        captcha_type = (data.get('captcha_type') or 'turnstile').strip()
        purpose = (data.get('purpose') or 'register').strip()  # 'register' | 'email_change' | 'password_change'
        captcha_pre_validated = data.get('captcha_pre_validated', False)  # 是否已通过预验证

        # 2) 轻量级拦截：先校验验证码（如果需要）
        if not captcha_pre_validated:
            # 统一验证码验证
            captcha_valid, captcha_error = verify_captcha_unified(
                request,
                turnstile_token=turnstile_token,
                image_captcha=image_captcha,
                captcha_type=captcha_type
            )
            if not captcha_valid:
                return JsonResponse({'status': 'error', 'message': captcha_error}, status=400)

        # 3) 获取真实客户端IP（支持代理环境）
        from knowledge_project.utils.request_utils import get_client_ip, check_rate_limit_atomic
        ip_address = get_client_ip(request)

        # 4) 原子操作限流检查 - 避免竞态条件
        # IP级别的限流（防止恶意攻击）
        ip_hourly_key = f"email_attempts_hourly_{ip_address}"
        ip_daily_key = f"email_attempts_daily_{ip_address}"

        ip_hourly_allowed, ip_hourly_attempts = check_rate_limit_atomic(ip_hourly_key, 3, 3600)
        if not ip_hourly_allowed:
            return JsonResponse({'status': 'error', 'message': '当前网络环境每小时请求过于频繁，请稍后再试。'}, status=429)

        ip_daily_allowed, ip_daily_attempts = check_rate_limit_atomic(ip_daily_key, 5, 86400)
        if not ip_daily_allowed:
            return JsonResponse({'status': 'error', 'message': '当前网络环境每天请求过于频繁，请稍后再试。'}, status=429)

        # 项目/用户级别的限流
        if request.user.is_authenticated:
            user_identifier = f"user_{request.user.id}"
        else:
            user_identifier = f"ip_{ip_address}"

        purpose_hourly_key = f"email_code_hourly_{purpose}_{user_identifier}"
        purpose_daily_key = f"email_code_daily_{purpose}_{user_identifier}"

        purpose_hourly_allowed, purpose_hourly_attempts = check_rate_limit_atomic(purpose_hourly_key, 3, 3600)
        if not purpose_hourly_allowed:
            return JsonResponse({
                'status': 'error',
                'message': '该操作每小时验证码发送已达上限（3次），请稍后再试。'
            }, status=429)

        purpose_daily_allowed, purpose_daily_attempts = check_rate_limit_atomic(purpose_daily_key, 5, 86400)
        if not purpose_daily_allowed:
            return JsonResponse({
                'status': 'error',
                'message': '该操作每天验证码发送已达上限（5次），请明天再试。'
            }, status=429)

        # 5) 业务区分 & 邮箱可用性检查（共用工具函数）
        if purpose == 'password_change':
            # 修改密码：发送验证码到当前邮箱，验证是本人操作
            if not request.user.is_authenticated:
                return JsonResponse({'status': 'error', 'message': '请先登录'}, status=403)

            # 使用当前用户的邮箱，不需要检查可用性
            email = request.user.email
            mail_subject = '密码修改验证码'
            ok_message   = '验证码已发送至您的邮箱'

        elif purpose == 'email_change':
            # 修改邮箱:发送验证码到新邮箱,验证新邮箱的所有权
            if not request.user.is_authenticated:
                return JsonResponse({'status': 'error', 'message': '未登录用户无法修改邮箱'}, status=403)

            # 禁止把新邮箱改成当前邮箱(防止滥发验证码)
            if email and request.user.email and email.lower() == request.user.email.lower():
                return JsonResponse({'status': 'error', 'message': '该邮箱与当前绑定邮箱一致,无需修改'}, status=400)

            # 修改邮箱:排除自己判断占用
            check = _check_email_availability(request, email, exclude_self=True)
            if not check['ok']:
                return JsonResponse({'status': 'error', 'message': check['message']}, status=400)

            mail_subject = '邮箱修改验证码'
            ok_message   = '验证码已发送至您的新邮箱'

        else:
            # 注册：谁绑了都算占用
            check = _check_email_availability(request, email, exclude_self=False)
            if not check['ok']:
                # 为了与之前前端体验一致，文案使用"已被注册"
                msg = '该邮箱已被注册' if check['reason'] == 'taken' else check['message']
                return JsonResponse({'status': 'error', 'message': msg}, status=400)

            mail_subject = '注册验证码'
            ok_message   = '验证码已发送至您的邮箱'

        # 6) 生成验证码
        email_code = ''.join(random.choices(string.digits, k=6))

        # 7) 把验证码写入 session（在发送邮件前就写入，确保状态一致）
        if purpose == 'email_change':
            session_key = 'email_change_verification'
        elif purpose == 'password_change':
            session_key = 'password_change_verification'
        else:
            session_key = 'registration_verification'

        # 构建验证信息对象
        verification_data = {
            'code': email_code,
            'email': email,
            'timestamp': time.time(),
            'purpose': purpose,
        }

        # 【用户体验改进】标记已通过人机验证
        if not captcha_pre_validated and turnstile_token:
            # 如果是通过Turnstile验证的，标记验证状态
            verification_data['turnstile_verified'] = True

        request.session[session_key] = verification_data
        request.session.modified = True

        # 8) 发送邮件（开发环境使用同步发送，生产环境建议使用异步）
        try:
            send_mail(
                mail_subject,
                f'您的{mail_subject}是：{email_code}。10分钟内有效。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            logger.info(f"验证码邮件发送成功 (IP: {ip_address}, Email: {email}, Purpose: {purpose})")
        except Exception as e:
            logger.error(f"邮件发送失败 (IP: {ip_address}, Email: {email}), 错误: {e}")
            # 发送失败时清理session中的验证码
            if session_key in request.session:
                del request.session[session_key]
            return JsonResponse({'status': 'error', 'message': '邮件发送失败，请稍后重试。'}, status=500)

        return JsonResponse({'status': 'success', 'message': ok_message})




# --- 视图：实时检查用户名是否存在 (新功能) ---
def check_username(request):
    """检查用户名是否可用"""
    username = request.GET.get("username", "").strip()
    if not username:
        return JsonResponse({"error": "Username not provided"}, status=400)
    # 正则检查
    if not USERNAME_REGEX.match(username):
        return JsonResponse({
            "is_taken": True,
            "message": "用户名至少6位，以小写字母开头，只能包含字母数字下划线"
        })
    # 查重
    is_taken = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({"is_taken": is_taken})


def check_email(request):
    """
    实时检查邮箱是否已被绑定
    - GET /check-email/?email=xxx[&exclude_self=1]
    - 返回：{'is_taken': bool, 'message': '...'(可选)}
    """
    email = request.GET.get('email', '').strip()
    exclude_self = request.GET.get('exclude_self') == '1'

    result = _check_email_availability(request, email, exclude_self=exclude_self)

    # 为了兼容你之前的前端，沿用 is_taken 字段
    # invalid 视为 is_taken=True，并返回 message（这样前端可以统一提示）
    if not result['ok']:
        return JsonResponse({'is_taken': True, 'message': result['message']})
    return JsonResponse({'is_taken': False})
