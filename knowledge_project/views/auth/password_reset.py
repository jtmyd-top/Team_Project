"""密码修改 / 忘记密码 / 密码重置。"""

import json
import threading

from ._shared import *
from .login import CustomLoginView
from .rate_limit import get_client_fingerprint, get_client_ip, check_rate_limit


def _send_email_async_helper(subject, body, recipients):
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        logger.info("Email sent to %s with subject %s", recipients, subject)
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)


def send_password_change_notification(request, user):
    try:
        profile = getattr(user, 'profile', None)
        if not profile or not profile.notify_password_change:
            return

        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')
        device_info = CustomLoginView().parse_user_agent(user_agent)
        change_time = timezone.localtime(timezone.now())

        email_subject = '账户密码修改通知'
        email_body = f"""
尊敬的 {user.username}：

您的账户密码已于 {change_time.strftime('%Y-%m-%d %H:%M:%S')} 被成功修改。

操作详情：
- 操作 IP 地址：{ip_address}
- 操作设备：{device_info}

如果这不是您本人的操作，请立即通过“忘记密码”功能重置密码，并检查账户安全设置。
"""

        threading.Thread(
            target=_send_email_async_helper,
            args=(email_subject, email_body, [user.email]),
            daemon=True,
        ).start()
    except Exception as exc:
        logger.error("Failed to send password change notification for user %s: %s", user.id, exc)


@login_required
@require_http_methods(["POST"])
def change_password(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    two_fa_code = data.get("two_fa_code", "").strip()
    use_backup = data.get("use_backup", False)

    if not all([current_password, new_password, confirm_password]):
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "当前密码错误"}, status=400)
    if new_password != confirm_password:
        return JsonResponse({"status": "error", "message": "两次输入的新密码不一致"}, status=400)
    if len(new_password) < 8:
        return JsonResponse({"status": "error", "message": "新密码长度至少为 8 位"}, status=400)

    profile = getattr(request.user, 'profile', None)
    if profile and profile.two_fa_enabled:
        if not two_fa_code:
            if profile.two_fa_method == 'email':
                from ...decorators import send_operation_2fa_email
                success, message = send_operation_2fa_email(request.user, operation_type='password_change')
                if not success:
                    return JsonResponse({'status': 'error', 'message': message}, status=429)

            return JsonResponse({
                'status': 'require_2fa',
                'message': '需要两因素认证以完成操作',
                'method': profile.two_fa_method,
            })

        from ...decorators import verify_2fa_for_request
        success, message = verify_2fa_for_request(request, two_fa_code, use_backup)
        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message,
            }, status=400)

    user = request.user
    user.set_password(new_password)
    user.save()

    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)
    send_password_change_notification(request, user)

    return JsonResponse({"status": "success", "message": "密码修改成功"})


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    return render(request, 'registration/forgot_password.html')


@require_http_methods(["POST"])
def password_reset_api(request):
    logger.info("[密码重置API] 收到请求")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "请求格式错误"}, status=400)

    email = data.get('email', '').strip()
    turnstile_token = data.get('turnstile_token', '').strip()
    image_captcha = data.get('image_captcha', '').strip()
    captcha_type = data.get('captcha_type', 'turnstile')

    if not email:
        return JsonResponse({"status": "error", "message": "请输入邮箱地址"}, status=400)

    captcha_valid, captcha_error = verify_captcha_unified(
        request,
        turnstile_token=turnstile_token,
        image_captcha=image_captcha,
        captcha_type=captcha_type,
    )
    if not captcha_valid:
        return JsonResponse({"status": "error", "message": captcha_error}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"status": "error", "message": "请输入正确的邮箱格式"}, status=400)

    client_ip = get_client_ip(request)
    fingerprint = get_client_fingerprint(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    is_allowed, rate_limit_message = check_rate_limit(email, client_ip, fingerprint, 3)
    if not is_allowed:
        return JsonResponse({"status": "error", "message": rate_limit_message}, status=429)

    from ...models import PasswordResetAttempt
    reset_attempt = PasswordResetAttempt.objects.create(
        email=email,
        ip_address=client_ip,
        fingerprint=fingerprint,
        user_agent=user_agent,
        is_successful=False,
    )

    try:
        user = User.objects.filter(email=email, is_active=True).first()
        if not user:
            return JsonResponse({"status": "success", "message": "如果该邮箱存在，重置邮件已发送"})

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        reset_url = request.build_absolute_uri(
            reverse('reset_password', kwargs={'user_id': user.id, 'token': token})
        )

        subject = '密码重置'
        body = f"请访问以下链接重置密码：\n{reset_url}\n\n该链接将在 12 小时后失效。"
        threading.Thread(
            target=_send_email_async_helper,
            args=(subject, body, [email]),
            daemon=True,
        ).start()

        reset_attempt.is_successful = True
        reset_attempt.save(update_fields=['is_successful'])
        return JsonResponse({"status": "success", "message": "如果该邮箱存在，重置邮件已发送"})
    except Exception as exc:
        logger.error("[密码重置API] error: %s", exc, exc_info=True)
        return JsonResponse({"status": "error", "message": "服务器内部错误"}, status=500)


def reset_password_view(request, user_id, token):
    user = get_object_or_404(User, id=user_id, is_active=True)
    token_generator = PasswordResetTokenGenerator()

    if not token_generator.check_token(user, token):
        return render(request, 'registration/reset_password.html', {
            'validlink': False,
            'message': '重置链接无效或已过期',
        })

    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not password or not confirm_password:
            return render(request, 'registration/reset_password.html', {
                'validlink': True,
                'error_message': '请输入并确认新密码',
            })
        if password != confirm_password:
            return render(request, 'registration/reset_password.html', {
                'validlink': True,
                'error_message': '两次输入的密码不一致',
            })
        if len(password) < 8:
            return render(request, 'registration/reset_password.html', {
                'validlink': True,
                'error_message': '密码长度至少为 8 位',
            })

        user.set_password(password)
        user.save()
        return render(request, 'registration/reset_password.html', {
            'validlink': False,
            'success_message': '密码已重置，请重新登录',
        })

    return render(request, 'registration/reset_password.html', {'validlink': True})
