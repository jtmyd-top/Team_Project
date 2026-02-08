# knowledge_project/admin_auth.py
"""
Django Admin 安全增强 - 自定义登录视图

功能：
1. 账户冻结检查
2. IP 封禁检查
3. 人机验证 (Turnstile/图片验证码)
4. 强制 2FA 认证（所有管理员必须）
5. 首次登录强制设置 2FA
"""

import time
import logging
import pyotp
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.conf import settings

logger = logging.getLogger(__name__)


class SecureAdminSite(AdminSite):
    """
    安全增强的 Admin 站点

    覆盖默认的登录流程，添加：
    - IP 封禁检查
    - 账户冻结检查
    - 人机验证
    - 强制 2FA
    """

    login_template = 'admin/secure_login.html'

    def login(self, request, extra_context=None):
        """自定义登录视图"""
        from .models import Profile

        # 获取客户端 IP
        ip_address = self._get_client_ip(request)

        # 检查 IP 封禁
        ban_key = f'banned_ip:{ip_address}'
        if cache.get(ban_key):
            return render(request, 'admin/banned.html', {
                'message': '您的 IP 已被封禁，禁止访问管理后台。'
            }, status=403)

        # 调试日志
        logger.debug(f"Admin login: method={request.method}, 2fa_pending={request.session.get('admin_2fa_pending')}, 2fa_setup={request.session.get('admin_2fa_setup_required')}")

        # 检查是否已经在 2FA 验证阶段（优先级最高）
        if request.session.get('admin_2fa_pending'):
            logger.debug("进入 2FA 验证流程")
            return self._handle_2fa_verification(request)

        # 检查是否在设置 2FA 阶段
        if request.session.get('admin_2fa_setup_required'):
            logger.debug("进入 2FA 设置流程")
            return self._handle_2fa_setup(request)

        # 只有不在 2FA 流程中才处理登录 POST
        if request.method == 'POST':
            return self._handle_login_post(request)

        # GET 请求，显示登录表单
        context = {
            'title': '管理后台登录',
            'site_title': self.site_title,
            'site_header': self.site_header,
            'turnstile_site_key': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
            'captcha_backend': getattr(settings, 'CAPTCHA_BACKEND', 'auto'),
            **(extra_context or {})
        }
        return render(request, self.login_template, context)

    def _handle_login_post(self, request):
        """处理登录 POST 请求"""
        from .models import Profile
        from .utils.turnstile import verify_turnstile_token
        from .views import verify_image_captcha
        from captcha.models import CaptchaStore
        from captcha.helpers import captcha_image_url

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        ip_address = self._get_client_ip(request)

        # 1. 验证人机验证
        turnstile_token = request.POST.get('turnstile_token', '')
        captcha_key = request.POST.get('captcha_0', '')
        captcha_value = request.POST.get('captcha_1', '')

        captcha_passed = False

        # 优先检查 Turnstile（不传IP，避免代理/NAT导致验证失败）
        if turnstile_token:
            result = verify_turnstile_token(turnstile_token)
            logger.info(f"Admin Turnstile验证: token长度={len(turnstile_token)}, 结果={result}")
            if result:
                captcha_passed = True

        # 其次检查 simple_captcha
        if not captcha_passed and captcha_key and captcha_value:
            try:
                captcha = CaptchaStore.objects.get(hashkey=captcha_key)
                if captcha.response.lower() == captcha_value.strip().lower():
                    captcha_passed = True
                captcha.delete()
            except CaptchaStore.DoesNotExist:
                pass

        # 开发模式跳过
        if not captcha_passed and not getattr(settings, 'TURNSTILE_ENABLED', True):
            captcha_passed = True

        if not captcha_passed:
            return self._login_error(request, '验证码错误或已过期，请重试')

        # 2. 验证用户名密码
        user = authenticate(request, username=username, password=password)
        if user is None:
            logger.warning(f"Admin 登录失败: 用户名或密码错误, IP: {ip_address}, 用户: {username}")
            return self._login_error(request, '用户名或密码错误')

        # 3. 检查是否是管理员
        if not user.is_staff:
            return self._login_error(request, '您没有管理后台访问权限')

        # 4. 检查账户是否激活
        if not user.is_active:
            return self._login_error(request, '账户已被禁用')

        # 5. 检查账户冻结
        user_lock_key = f'vault_user_lock:{user.id}'
        user_lock_expire = cache.get(user_lock_key)
        if user_lock_expire:
            remaining = user_lock_expire - int(time.time())
            if remaining > 0:
                remaining_minutes = max(1, remaining // 60)
                return self._login_error(request, f'账户已被冻结，请在 {remaining_minutes} 分钟后重试')

        # 6. 检查 2FA 状态
        profile = getattr(user, 'profile', None)

        if profile and profile.two_fa_enabled:
            # 已启用 2FA，进入验证阶段
            request.session['admin_2fa_pending'] = True
            request.session['admin_2fa_user_id'] = user.id
            request.session['admin_2fa_method'] = profile.two_fa_method
            request.session.modified = True  # 确保 session 被保存

            # 如果是邮箱验证，发送验证码
            if profile.two_fa_method == 'email':
                self._send_email_2fa_code(user, request)

            return redirect(request.path)
        else:
            # 未启用 2FA，强制设置
            request.session['admin_2fa_setup_required'] = True
            request.session['admin_2fa_user_id'] = user.id
            request.session.modified = True  # 确保 session 被保存

            # 生成 TOTP 密钥
            totp_secret = pyotp.random_base32()
            request.session['admin_2fa_totp_secret'] = totp_secret

            return redirect(request.path)

    def _handle_2fa_verification(self, request):
        """处理 2FA 验证"""
        from .models import Profile

        user_id = request.session.get('admin_2fa_user_id')
        two_fa_method = request.session.get('admin_2fa_method', 'totp')

        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
        except (User.DoesNotExist, Profile.DoesNotExist):
            self._clear_2fa_session(request)
            return self._login_error(request, '会话已过期，请重新登录')

        # 检查 2FA 失败次数
        attempt_key = f'admin_2fa_attempts:{user_id}'
        attempts = cache.get(attempt_key, 0)
        if attempts >= 5:
            self._clear_2fa_session(request)
            return self._login_error(request, '验证码错误次数过多，请5分钟后重新登录')

        if request.method == 'POST':
            code = request.POST.get('code', '').strip()
            use_backup = request.POST.get('use_backup', '') == 'true'
            verified = False

            if use_backup:
                if profile.backup_codes:
                    import hashlib
                    code_hash = hashlib.sha256(code.encode()).hexdigest()
                    if code_hash in profile.backup_codes:
                        profile.backup_codes.remove(code_hash)
                        profile.save(update_fields=['backup_codes'])
                        verified = True
            elif two_fa_method == 'totp':
                totp = pyotp.TOTP(profile.totp_secret)
                if totp.verify(code, valid_window=1):
                    verified = True
            else:
                cache_key = f'admin_2fa_email_code:{user_id}'
                stored_code = cache.get(cache_key)
                if stored_code and stored_code == code:
                    cache.delete(cache_key)
                    verified = True

            if verified:
                cache.delete(attempt_key)
                return self._complete_login(request, user)

            # 失败，递增计数
            cache.set(attempt_key, attempts + 1, timeout=300)
            remaining = 4 - attempts
            if remaining <= 0:
                self._clear_2fa_session(request)
                return self._login_error(request, '验证码错误次数过多，请5分钟后重新登录')
            return self._2fa_error(request, f'验证码错误，还剩 {remaining} 次机会', two_fa_method)

        # GET 请求，显示 2FA 验证表单
        context = {
            'title': '两因素认证',
            'two_fa_method': two_fa_method,
            'username': user.username,
        }
        return render(request, 'admin/2fa_verify.html', context)

    def _handle_2fa_setup(self, request):
        """处理首次登录的 2FA 设置"""
        from .models import Profile

        user_id = request.session.get('admin_2fa_user_id')
        totp_secret = request.session.get('admin_2fa_totp_secret')

        try:
            user = User.objects.get(id=user_id)
            profile, _ = Profile.objects.get_or_create(user=user)
        except User.DoesNotExist:
            self._clear_2fa_session(request)
            return self._login_error(request, '会话已过期，请重新登录')

        if request.method == 'POST':
            code = request.POST.get('code', '').strip()

            # 验证 TOTP 码
            totp = pyotp.TOTP(totp_secret)
            if totp.verify(code, valid_window=1):
                # 保存 2FA 设置
                profile.totp_secret = totp_secret
                profile.two_fa_enabled = True
                profile.two_fa_method = 'totp'

                # 生成备用码
                import secrets
                backup_codes = [secrets.token_hex(4).upper() for _ in range(5)]
                profile.backup_codes = ','.join(backup_codes)

                profile.save()

                # 清除设置状态，显示备用码
                request.session['admin_2fa_backup_codes'] = backup_codes
                request.session['admin_2fa_setup_complete'] = True
                del request.session['admin_2fa_setup_required']
                del request.session['admin_2fa_totp_secret']

                return redirect(request.path)
            else:
                return self._2fa_setup_error(request, '验证码错误，请重试', user, totp_secret)

        # 检查是否刚完成设置，显示备用码
        if request.session.get('admin_2fa_setup_complete'):
            backup_codes = request.session.get('admin_2fa_backup_codes', [])
            del request.session['admin_2fa_setup_complete']
            del request.session['admin_2fa_backup_codes']

            context = {
                'title': '保存您的备用验证码',
                'backup_codes': backup_codes,
                'username': user.username,
            }
            return render(request, 'admin/2fa_backup_codes.html', context)

        # GET 请求，显示 2FA 设置表单
        import qrcode
        import base64
        from io import BytesIO

        totp = pyotp.TOTP(totp_secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email or user.username,
            issuer_name='Knowledge Admin'
        )

        # 生成 QR 码
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        context = {
            'title': '设置两因素认证',
            'username': user.username,
            'totp_secret': totp_secret,
            'qr_code': qr_code_base64,
        }
        return render(request, 'admin/2fa_setup.html', context)

    def _complete_login(self, request, user):
        """完成登录"""
        self._clear_2fa_session(request)
        login(request, user)
        logger.info(f"Admin 登录成功: {user.username}, IP: {self._get_client_ip(request)}")

        # 重定向到 Admin 首页
        return redirect('/admin/')

    def _send_email_2fa_code(self, user, request):
        """发送邮箱 2FA 验证码"""
        import secrets
        from django.core.mail import send_mail

        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        cache_key = f'admin_2fa_email_code:{user.id}'
        cache.set(cache_key, code, timeout=300)  # 5分钟有效

        try:
            send_mail(
                subject='管理后台登录验证码',
                message=f'您的管理后台登录验证码是：{code}\n\n验证码5分钟内有效。',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"发送 Admin 2FA 邮件失败: {e}")

    def _login_error(self, request, message):
        """返回登录错误页面"""
        context = {
            'title': '管理后台登录',
            'site_title': self.site_title,
            'site_header': self.site_header,
            'error_message': message,
            'turnstile_site_key': getattr(settings, 'CLOUDFLARE_TURNSTILE_SITE_KEY', ''),
            'captcha_backend': getattr(settings, 'CAPTCHA_BACKEND', 'auto'),
        }
        return render(request, self.login_template, context)

    def _2fa_error(self, request, message, two_fa_method):
        """返回 2FA 验证错误"""
        user_id = request.session.get('admin_2fa_user_id')
        user = User.objects.get(id=user_id)
        context = {
            'title': '两因素认证',
            'two_fa_method': two_fa_method,
            'username': user.username,
            'error_message': message,
        }
        return render(request, 'admin/2fa_verify.html', context)

    def _2fa_setup_error(self, request, message, user, totp_secret):
        """返回 2FA 设置错误"""
        import qrcode
        import base64
        from io import BytesIO

        totp = pyotp.TOTP(totp_secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email or user.username,
            issuer_name='Knowledge Admin'
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        context = {
            'title': '设置两因素认证',
            'username': user.username,
            'totp_secret': totp_secret,
            'qr_code': qr_code_base64,
            'error_message': message,
        }
        return render(request, 'admin/2fa_setup.html', context)

    def _clear_2fa_session(self, request):
        """清除 2FA 相关 session"""
        keys = [
            'admin_2fa_pending',
            'admin_2fa_user_id',
            'admin_2fa_method',
            'admin_2fa_setup_required',
            'admin_2fa_totp_secret',
        ]
        for key in keys:
            if key in request.session:
                del request.session[key]

    def _get_client_ip(self, request):
        """获取客户端 IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


# 创建安全 Admin 站点实例
secure_admin_site = SecureAdminSite(name='secure_admin')
