"""密码修改 / 忘记密码 / 密码重置。"""
from ._shared import *
from .login import CustomLoginView
from .rate_limit import get_client_ip, get_client_fingerprint, check_rate_limit


def _send_email_async_helper(subject, body, recipients):
    """
    异步发送邮件的辅助函数（用于笔记活动通知）
    """
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipients} with subject '{subject}'")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def send_password_change_notification(request, user):
    """
    发送密码修改成功通知邮件（独立函数版本）
    """
    try:
        profile = getattr(user, 'profile', None)
        if not profile or not profile.notify_password_change:
            return

        # 获取IP地址
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()
        else:
            ip_address = request.META.get('HTTP_X_REAL_IP')
            if not ip_address:
                ip_address = request.META.get('REMOTE_ADDR', '未知')

        # 解析User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '未知设备')
        device_info = CustomLoginView().parse_user_agent(user_agent)

        change_time = timezone.localtime(timezone.now())

        email_subject = '账户密码修改通知'
        email_body = f"""
尊敬的 {user.username}：

您的账户密码已于 {change_time.strftime('%Y年%m月%d日 %H:%M:%S')} 被成功修改。

操作详情：
- 操作IP地址：{ip_address}
- 操作设备：{device_info}

如果这不是您本人的操作，您的账户可能存在安全风险。请立即通过"忘记密码"功能重置您的密码，并检查您的账户安全设置。

此邮件为系统自动发送，请勿回复。

知识管理系统
        """

        threading.Thread(
            target=_send_email_async_helper,
            args=(email_subject, email_body, [user.email]),
            daemon=True
        ).start()

        logger.info(f"Password change notification queued for user {user.id}")

    except Exception as e:
        logger.error(f"Failed to send password change notification for user {user.id}: {e}")


@login_required
@require_http_methods(["POST"])
def change_password(request):
    """
    修改密码 (安全分步验证版)
    1. 验证当前密码和新密码
    2. 如果需要，再验证 2FA
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "JSON 格式错误"}, status=400)

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    two_fa_code = data.get("two_fa_code", "").strip()
    use_backup = data.get("use_backup", False)

    # 1) 基础验证
    if not all([current_password, new_password, confirm_password]):
        return JsonResponse({"status": "error", "message": "缺少必要参数"}, status=400)
    if not request.user.check_password(current_password):
        return JsonResponse({"status": "error", "message": "当前密码错误"}, status=400)
    if new_password != confirm_password:
        return JsonResponse({"status": "error", "message": "两次输入的新密码不一致"}, status=400)
    if len(new_password) < 8:
        return JsonResponse({"status": "error", "message": "新密码长度至少为8位"}, status=400)

    # 2) 检查并执行 2FA 验证
    profile = getattr(request.user, 'profile', None)
    if profile and profile.two_fa_enabled:
        if not two_fa_code:
            # 如果需要 2FA 但未提供验证码，则要求输入
            if profile.two_fa_method == 'email':
                from ...decorators import send_operation_2fa_email
                success, message = send_operation_2fa_email(request.user, operation_type='password_change')
                if not success:
                    return JsonResponse({
                        'status': 'error',
                        'message': message
                    }, status=429)

            return JsonResponse({
                'status': 'require_2fa',
                'message': '需要两因素认证以完成操作',
                'method': profile.two_fa_method
            })

        # 如果提供了 2FA 验证码，则进行验证
        from ...decorators import verify_2fa_for_request
        success, message = verify_2fa_for_request(request, two_fa_code, use_backup)
        if not success:
            return JsonResponse({
                'status': 'error',
                'code': 'invalid_2fa',
                'message': message
            }, status=400)
        # 2FA 验证通过，继续执行

    # 3) 所有验证通过，更新密码
    user = request.user
    user.set_password(new_password)
    user.save()

    # 重新登录用户（因为密码已更改）
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)

    # 发送密码修改通知
    send_password_change_notification(request, user)

    return JsonResponse({"status": "success", "message": "密码修改成功"})


# ==================== 忘记密码功能 ====================

def forgot_password_view(request):
    """
    忘记密码页面
    """
    # 如果用户已登录，重定向到主页
    if request.user.is_authenticated:
        return redirect('/')

    return render(request, 'registration/forgot_password.html')


@require_http_methods(["POST"])
def password_reset_api(request):
    """
    密码重置API（增强安全版本）
    POST: 发送重置密码邮件（需要验证码和频率限制）
    支持 Turnstile 和图形验证码双模式
    """
    logger.info("[密码重置API] 收到请求")

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            logger.info(f"[密码重置API] 请求邮箱: {email}")

            # 验证码参数：支持 turnstile 和图形验证码
            turnstile_token = data.get('turnstile_token', '').strip()
            image_captcha = data.get('image_captcha', '').strip()
            captcha_type = data.get('captcha_type', 'turnstile')

            # 验证必要参数
            if not email:
                return JsonResponse({
                    "status": "error",
                    "message": "请输入邮箱地址"
                }, status=400)

            # 统一验证码验证
            captcha_valid, captcha_error = verify_captcha_unified(
                request,
                turnstile_token=turnstile_token,
                image_captcha=image_captcha,
                captcha_type=captcha_type
            )
            if not captcha_valid:
                return JsonResponse({
                    "status": "error",
                    "message": captcha_error
                }, status=400)

            # 验证邮箱格式
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({
                    "status": "error",
                    "message": "请输入正确的邮箱格式"
                }, status=400)

            # 获取客户端信息用于频率限制
            client_ip = get_client_ip(request)
            fingerprint = get_client_fingerprint(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # 限制长度

            # 检查频率限制（原有每日/设备/IP限制）
            is_allowed, rate_limit_message = check_rate_limit(email, client_ip, fingerprint, 3)
            if not is_allowed:
                return JsonResponse({
                    "status": "error",
                    "message": rate_limit_message
                }, status=429)

            from ...models import PasswordResetAttempt

            # 创建密码重置尝试记录（用于频率限制跟踪）
            reset_attempt = PasswordResetAttempt.objects.create(
                email=email,
                ip_address=client_ip,
                fingerprint=fingerprint,
                user_agent=user_agent,
                is_successful=False  # 默认为失败，成功发送邮件后会更新
            )

            # 检查邮箱是否存在
            try:
                user = User.objects.get(email=email)
                user_exists = True
                logger.info(f"[密码重置] 邮箱 {email} 存在，用户: {user.username}")
            except User.DoesNotExist:
                # 邮箱不存在，但继续执行以确保响应时间一致
                user_exists = False
                logger.info(f"[密码重置] 邮箱 {email} 不存在于系统中")

            # 为了防止时序攻击，无论邮箱是否存在都执行相同的操作
            import time
            import secrets
            import string
            from ...models import PasswordResetToken

            # 模拟token生成时间（无论邮箱是否存在）
            time.sleep(0.1)  # 固定延时确保响应时间一致

            # 生成随机token（即使邮箱不存在也生成，防止时序攻击）
            alphabet = string.ascii_letters + string.digits
            dummy_token = ''.join(secrets.choice(alphabet) for _ in range(64))

            # 只有邮箱存在时才实际处理
            if user_exists:
                # 删除旧的令牌（如果存在）
                PasswordResetToken.objects.filter(user=user).delete()

                # 创建新的令牌
                reset_token = PasswordResetToken.objects.create(
                    user=user,
                    token=dummy_token
                )

                # 构建重置URL
                reset_url = f"{request.scheme}://{request.get_host()}/reset-password/{user.pk}/{dummy_token}/"

                # 发送邮件
                from django.core.mail import send_mail
                from django.conf import settings

                subject = '重置您的密码'
                message = f'''
                您好，{user.username}！

                您请求重置密码。请点击以下链接重置密码：
                {reset_url}

                此链接将在24小时后失效。

                如果您没有请求重置密码，请忽略此邮件。
                '''

                try:
                    logger.info(f"[密码重置] 准备发送邮件到: {email}")
                    logger.info(f"[密码重置] 发件人: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')}")
                    logger.info(f"[密码重置] SMTP配置: HOST={settings.EMAIL_HOST}, PORT={settings.EMAIL_PORT}, USER={settings.EMAIL_HOST_USER}")

                    result = None
                    send_success = False
                    error_message = None

                    # 尝试使用代理发送（如果配置了代理）
                    try:
                        from knowledge_project.utils.proxy_email_sender import send_mail_with_proxy
                        success, msg = send_mail_with_proxy(
                            subject=subject,
                            message=message,
                            recipient_list=[email],
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
                        )

                        if success:
                            result = 1
                            send_success = True
                            logger.info(f"[密码重置] 邮件发送成功: {msg}")
                        else:
                            logger.warning(f"[密码重置] 代理发送失败: {msg}，尝试直连发送")
                    except ImportError:
                        logger.info(f"[密码重置] 代理模块未安装，使用直连发送")
                    except Exception as proxy_error:
                        logger.warning(f"[密码重置] 代理发送异常: {proxy_error}，尝试直连发送")

                    # 如果代理未成功，尝试直连
                    if not send_success:
                        try:
                            result = send_mail(
                                subject=subject,
                                message=message,
                                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                                recipient_list=[email],
                                fail_silently=False
                            )
                            send_success = True
                            logger.info(f"[密码重置] 直连发送成功: {result}")
                        except Exception as direct_error:
                            error_message = str(direct_error)
                            logger.error(f"[密码重置] 直连也失败: {error_message}")

                    # 标记尝试状态
                    if send_success:
                        reset_attempt.is_successful = True
                        reset_attempt.save()
                    else:
                        logger.warning(f"[密码重置] 邮件发送最终失败: {error_message}")

                except Exception as e:
                    logger.error(f"[密码重置] 发送邮件异常: {str(e)}", exc_info=True)

            # 统一返回消息，不暴露邮箱是否存在
            return JsonResponse({
                "status": "success",
                "message": "如果该邮箱地址已注册，重置密码链接已发送到该邮箱"
            })

        except json.JSONDecodeError:
            return JsonResponse({
                "status": "error",
                "message": "请求格式错误"
            }, status=400)
        except Exception as e:
            logger.error(f"密码重置请求失败: {str(e)}")
            return JsonResponse({
                "status": "error",
                "message": "服务器错误，请稍后重试"
            }, status=500)

    return JsonResponse({
        "status": "error",
        "message": "不支持的请求方法"
    }, status=405)


def reset_password_view(request, user_id, token):
    """
    重置密码页面
    GET: 显示重置密码表单
    POST: 处理密码重置
    """
    # 如果用户已登录，重定向到主页
    if request.user.is_authenticated:
        return redirect('/')

    from django.contrib.auth.models import User
    from django.contrib.auth import login, update_session_auth_hash
    from ...models import PasswordResetToken

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return render(request, 'registration/reset_password.html', {
            'error': '无效的重置链接'
        })

    # 使用新的Token模型验证
    try:
        reset_token = PasswordResetToken.objects.get(user=user, token=token)

        # 检查令牌是否已使用或过期
        if reset_token.is_used or reset_token.is_expired:
            if reset_token.is_used:
                error_message = '重置链接已被使用，如需重置密码，请重新申请'
            else:
                remaining_time = reset_token.get_remaining_time()
                if remaining_time == 0:
                    error_message = '重置链接已过期（24小时有效期），请重新申请密码重置'
                else:
                    error_message = f'重置链接无效'

            return render(request, 'registration/reset_password.html', {
                'error': error_message,
                'user_id': user_id,
                'token': token,
                'username': user.username
            })

    except PasswordResetToken.DoesNotExist:
        return render(request, 'registration/reset_password.html', {
            'error': '无效的重置链接',
            'user_id': user_id,
            'token': token,
            'username': user.username
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST.dict()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')

            if not password or not confirm_password:
                if request.content_type == 'application/json':
                    return JsonResponse({
                        "status": "error",
                        "message": "请填写所有字段"
                    }, status=400)
                else:
                    return render(request, 'registration/reset_password.html', {
                        'error': '请填写所有字段',
                        'user_id': user_id,
                        'token': token
                    })

            if password != confirm_password:
                if request.content_type == 'application/json':
                    return JsonResponse({
                        "status": "error",
                        "message": "两次输入的密码不一致"
                    }, status=400)
                else:
                    return render(request, 'registration/reset_password.html', {
                        'error': '两次输入的密码不一致',
                        'user_id': user_id,
                        'token': token
                    })

            # 验证密码强度
            if len(password) < 8:
                if request.content_type == 'application/json':
                    return JsonResponse({
                        "status": "error",
                        "message": "密码长度至少为8位"
                    }, status=400)
                else:
                    return render(request, 'registration/reset_password.html', {
                        'error': '密码长度至少为8位',
                        'user_id': user_id,
                        'token': token
                    })

            # 更新密码
            user.set_password(password)
            user.save()

            # 标记令牌为已使用
            reset_token.is_used = True
            reset_token.save(update_fields=['is_used'])

            # 清除所有 vault 锁定和失败计数（设备级 + 用户级 + IP级）
            from django.core.cache import cache as _cache

            # 1. 用户级：直接按 user_id 清除
            for prefix in ['vault_user_lock', 'vault_user_fail', 'vault_fail', 'vault_lock']:
                _cache.delete(f'{prefix}:{user.id}')

            # 2. 设备级：通过 Redis 模式匹配清除 session-based 的 vault key
            try:
                from django_redis import get_redis_connection
                conn = get_redis_connection('default')
                for pattern in ['*vault_fail*', '*vault_lock*']:
                    for k in conn.keys(pattern):
                        conn.delete(k)
            except Exception:
                pass

            # 3. IP级：清除当前IP及用户关联IP的封禁
            try:
                from ...models import AccessLog
                from ...decorators import get_client_ip

                # 获取当前请求IP
                current_ip = get_client_ip(request)
                ips_to_clear = {current_ip} if current_ip else set()

                # 查找该用户关联的所有IP（从AccessLog中）
                user_ips = AccessLog.objects.filter(
                    user_identifier=user.username,
                    action='vault_fail'
                ).values_list('ip_address', flat=True).distinct()
                ips_to_clear.update(user_ips)

                # 清除所有关联IP的封禁和失败记录
                for ip in ips_to_clear:
                    if ip:
                        _cache.delete(f'banned_ip:{ip}')

                # 清除该用户的AccessLog失败记录（重置IP级计数）
                AccessLog.objects.filter(
                    user_identifier=user.username,
                    action__in=['vault_fail', 'ip_banned']
                ).delete()

                logger.info(f"密码重置: 已清除用户 {user.username} 的IP级限制, IPs: {ips_to_clear}")
            except Exception as e:
                logger.error(f"密码重置: 清除IP级限制失败: {e}")

            # 【重要】解除保密柜锁定
            from ...signals import on_password_reset
            on_password_reset(user)

            # 自动登录用户
            login(request, user)

            if request.content_type == 'application/json':
                return JsonResponse({
                    "status": "success",
                    "message": "密码重置成功，正在跳转到首页...",
                    "redirect_url": "/"
                })
            else:
                # 传统表单提交，重定向到首页
                return redirect('home')

        except Exception as e:
            logger.error(f"重置密码失败: {str(e)}")
            if request.content_type == 'application/json':
                return JsonResponse({
                    "status": "error",
                    "message": "重置密码失败，请稍后重试"
                }, status=500)
            else:
                return render(request, 'registration/reset_password.html', {
                    'error': '重置密码失败，请稍后重试',
                    'user_id': user_id,
                    'token': token
                })

    # GET请求：显示重置密码表单
    return render(request, 'registration/reset_password.html', {
        'user_id': user_id,
        'token': token,
        'username': user.username
    })
