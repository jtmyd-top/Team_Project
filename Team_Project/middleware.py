"""
Django 中间件 - 用于设置安全响应头、IP 封禁和保密柜锁定检查
"""
import logging
import json
import time
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.core.cache import cache

logger = logging.getLogger(__name__)


class IPBanMiddleware:
    """
    IP 封禁中间件

    检查请求 IP 是否在 Redis 黑名单中（key: banned_ip:<ip>）。
    如果命中，直接返回 403 拒绝访问。

    放在 MIDDLEWARE 列表靠前位置，在认证之前拦截，
    这样被封禁的 IP 连登录页面都无法加载。
    """

    # 允许被封禁 IP 访问的路径（避免完全白屏）
    EXEMPT_PREFIXES = [
        '/static/',
        '/forgot-password/',
        '/api/forgot-password/',
        '/api/reset-password/',
        '/reset-password/',
        '/captcha/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("IPBanMiddleware initialized")

    def __call__(self, request):
        ip = self._get_client_ip(request)

        # 跳过静态资源
        for prefix in self.EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return self.get_response(request)

        if ip and cache.get(f'banned_ip:{ip}'):
            logger.warning(f"IPBanMiddleware: blocked request from banned IP {ip} to {request.path}")
            if request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
                return JsonResponse({
                    'status': 'error',
                    'message': '您的 IP 已被封禁，禁止访问。',
                }, status=403)
            return HttpResponse(
                '<h1>403 Forbidden</h1><p>您的 IP 已被封禁，禁止访问。</p>',
                status=403,
                content_type='text/html; charset=utf-8',
            )

        return self.get_response(request)

    def _get_client_ip(self, request):
        """获取客户端真实 IP（支持 Nginx 代理透传）"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip.strip()
        return request.META.get('REMOTE_ADDR')


class ContentSecurityPolicyMiddleware:
    """
    设置 Content-Security-Policy 响应头

    注意：认证页面（使用 Turnstile）不设置 CSP，因为 Turnstile 对 CSP 有严格要求
    """

    # 需要跳过 CSP 的路径（认证相关页面使用 Turnstile）
    AUTH_PATHS = ['/login', '/signup', '/forgot-password', '/reset-password']

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("✅ ContentSecurityPolicyMiddleware initialized")

    def __call__(self, request):
        response = self.get_response(request)

        # 检查是否是认证页面（需要 Turnstile）
        path = request.path.rstrip('/')
        is_auth_page = any(path == auth_path or path.startswith(auth_path + '/') for auth_path in self.AUTH_PATHS)

        # 调试日志
        logger.info(f"🔍 CSP Middleware: path={request.path}, is_auth_page={is_auth_page}")

        if is_auth_page:
            # 认证页面不设置 CSP，让 Turnstile 正常工作
            logger.info(f"⏭️ Skipping CSP for auth page: {request.path}")
            return response

        # 其他页面设置标准 CSP（包含 Turnstile 域名）
        csp_header = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: "
            "https://cdn.jsdelivr.net "
            "https://fastly.jsdelivr.net "
            "https://unpkg.com "
            "https://cdnjs.cloudflare.com "
            "https://live2d.03vps.cn "
            "https://cubism.live2d.com "
            "https://static.cloudflareinsights.com "
            "https://challenges.cloudflare.com; "
            "frame-src 'self' https://challenges.cloudflare.com https://i.y.qq.com https://y.qq.com https://music.163.com; "
            "connect-src 'self' https://cdn.jsdelivr.net https://fastly.jsdelivr.net https://cdnjs.cloudflare.com https://live2d.03vps.cn https://static.cloudflareinsights.com https://challenges.cloudflare.com https://c6.y.qq.com https://i.y.qq.com https://y.qq.com https://music.163.com; "
            "worker-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "img-src 'self' data: https: blob:; "
            "font-src 'self' data: https:; "
            "media-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        response['Content-Security-Policy'] = csp_header
        return response


class SessionTimeoutMiddleware:
    """
    服务端登录态超时兜底。

    保留 Django 的滚动过期行为，同时记录最近活动时间，避免首页在线人数只靠
    expire_date 反推导致统计不准。
    """

    STARTED_AT_KEY = 'auth_started_at'
    LAST_ACTIVITY_KEY = 'last_activity_at'
    EXEMPT_PREFIXES = (
        '/static/',
        '/uploads/',
        '/media/',
        '/captcha/',
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.idle_timeout = int(getattr(settings, 'SESSION_IDLE_TIMEOUT', settings.SESSION_COOKIE_AGE))
        logger.info(
            "SessionTimeoutMiddleware initialized: idle=%ss",
            self.idle_timeout,
        )

    def __call__(self, request):
        if self._should_check(request):
            expired_response = self._expire_if_needed(request)
            if expired_response is not None:
                return expired_response
            self._touch(request)

        response = self.get_response(request)

        if getattr(request, 'user', None) is not None and request.user.is_authenticated:
            self._ensure_metadata(request)

        return response

    def _should_check(self, request):
        if getattr(request, 'user', None) is None or not request.user.is_authenticated:
            return False
        return not any(request.path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)

    def _expire_if_needed(self, request):
        now = int(time.time())
        started_at = request.session.get(self.STARTED_AT_KEY)
        last_activity_at = request.session.get(self.LAST_ACTIVITY_KEY)

        if not started_at:
            request.session[self.STARTED_AT_KEY] = now

        if not last_activity_at:
            request.session[self.LAST_ACTIVITY_KEY] = now
            return None

        if self.idle_timeout > 0 and now - int(last_activity_at) > self.idle_timeout:
            return self._expire(request, 'idle_timeout')

        return None

    def _touch(self, request):
        now = int(time.time())
        request.session[self.LAST_ACTIVITY_KEY] = now
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)

    def _ensure_metadata(self, request):
        now = int(time.time())
        changed = False

        if not request.session.get(self.STARTED_AT_KEY):
            request.session[self.STARTED_AT_KEY] = now
            changed = True

        if not request.session.get(self.LAST_ACTIVITY_KEY):
            request.session[self.LAST_ACTIVITY_KEY] = now
            changed = True

        if changed:
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)

    def _expire(self, request, reason):
        user_id = getattr(request.user, 'id', None)
        logger.info("Session expired for user %s: %s", user_id, reason)
        logout(request)

        if self._is_api_request(request):
            return JsonResponse({
                'status': 'session_expired',
                'code': 'session_expired',
                'message': '登录已过期，请重新登录。',
            }, status=401)

        login_url = settings.LOGIN_URL if str(settings.LOGIN_URL).startswith('/') else f'/{settings.LOGIN_URL}/'
        query = urlencode({'next': request.get_full_path()})
        return redirect(f'{login_url}?{query}')

    def _is_api_request(self, request):
        return (
            request.path.startswith('/api/')
            or 'application/json' in request.headers.get('Accept', '')
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Content-Type', '')
        )


class VaultLockMiddleware:
    """
    保密柜锁定中间件（增强版 v2.0）

    当用户的保密柜被锁定时（验证失败次数过多），实施全面的访问限制：

    安全策略：
    1. 防篡改 (Integrity)：阻止所有写入操作（POST/PUT/PATCH/DELETE）
    2. 防泄漏 (Confidentiality)：阻止读取敏感数据（笔记内容、个人信息等）
    3. 防死锁 (Anti-Deadlock)：允许关键操作（登出、密码重置）穿透锁定

    关键问题解决 - Zombie Session 防护：
    当用户被锁定时，如果无法执行 POST /logout/ 请求，会导致以下安全隐患：
    - 前端删除了 Cookie（用户以为已登出）
    - 但后端会话 (Session) 未被销毁
    - 攻击者盗取的 Token 仍然有效
    -> 这被称为 "假性登出" (Fake Logout) 或 "殭屍会话" (Zombie Session)

    解决方案：通过 WRITE_METHOD_WHITELIST 允许关键操作即使在锁定状态下也能执行：
    - POST /logout/ -> 销毁服务器会话
    - POST /api/password-reset/ -> 重置密码解除锁定

    锁定状态下允许的操作：
    - 认证相关：登录、登出、密码重置、2FA重发
    - 保密柜相关：验证、状态查询
    - 静态资源：CSS、JS、图片等
    - 基础页面：首页（不含敏感数据）

    ⚠️ 特殊：以下写入操作即使被锁定也允许（白名单）
    - POST /logout/ -> 真正销毁会话，防止 Zombie Session
    - POST /api/password-reset/ -> 重置密码以解除锁定
    - POST /api/2fa/resend-email/ -> 重发2FA邮件

    锁定状态下阻止的操作：
    - 所有其他写入操作（创建、编辑、删除笔记等）
    - 读取笔记内容和列表
    - 读取用户设置和个人信息
    - 读取文件夹内容
    """

    # 允许的路径（即使被锁定也可以访问）
    ALLOWED_PATHS = [
        '/',
        '/login',
        '/logout',
        '/signup',
        '/forgot-password',
        '/reset-password',
        '/api/vault/verify/',
        '/api/vault/lock-status/',
        '/api/vault/send-email-code/',
        '/api/captcha/',
        '/api/captcha/init/',
        '/api/check-email/',
        '/api/check-username/',
        '/api/send-email-code/',
        '/api/password-reset/',
        '/api/turnstile/config/',
    ]

    # 白名单：允许的 POST/PUT/PATCH/DELETE 操作（即使被锁定也可以执行）
    # 这是为了防止 "假性登出" (Zombie Session) 的安全隐患
    # 用户被锁定时仍需能够：
    #   1. 真正登出（销毁服务器会话）
    #   2. 重置密码（解除锁定）
    WRITE_METHOD_WHITELIST = [
        ('POST', '/logout'),
        ('POST', '/api/logout/'),
        ('POST', '/forgot-password/'),
        ('POST', '/api/password-reset/'),
        ('POST', '/api/2fa/resend-email/'),
        ('GET', '/api/password-reset/'),  # 获取重置状态
    ]

    # 允许的路径前缀（静态资源等）
    # 注意：/admin/ 已移除，锁定用户也不能访问Django管理后台
    ALLOWED_PATH_PREFIXES = [
        '/static/',
        '/uploads/',
        '/ckeditor5/',
    ]

    # 敏感数据路径（即使是 GET 请求也要阻止）
    SENSITIVE_DATA_PATHS = [
        '/api/notes/',
        '/api/folders/',
        '/api/settings/',
        '/api/profile/',
        '/api/user/',
        '/api/sidebar/',
        '/knowledge/',
        '/admin/',  # Django 管理后台也视为敏感数据
    ]

    # 敏感数据路径前缀
    SENSITIVE_DATA_PREFIXES = [
        '/api/notes/',
        '/api/folders/',
        '/api/settings/',
        '/api/profile/',
        '/api/user/',
        '/protected_uploads/',
        '/admin/',  # Django 管理后台
        '/dashboard/',  # 战情室
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("✅ VaultLockMiddleware initialized (Enhanced)")

    def __call__(self, request):
        # 只检查已登录用户
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 检查是否是允许的路径（优先级最高）
        path = request.path
        if self._is_allowed_path(path):
            return self.get_response(request)

        # 检查用户是否被锁定
        if self._is_user_locked(request.user.id):
            # 检查是否是写入操作白名单（允许登出、密码重置等即使在锁定状态）
            if self._is_write_method_whitelisted(request.method, path):
                logger.info(f"✅ VaultLockMiddleware: 用户 {request.user.id} 被锁定，但 {request.method} {path} 在白名单中，允许执行")
                return self.get_response(request)

            # 检查是否是敏感数据读取（即使是 GET 也要阻止）
            if self._is_sensitive_data_path(path):
                logger.warning(f"🔒 VaultLockMiddleware: 用户 {request.user.id} 被锁定，阻止敏感数据访问: {request.method} {path}")
                return self._locked_response(request, is_read_blocked=True)

            # 阻止所有写入操作
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                logger.warning(f"🔒 VaultLockMiddleware: 用户 {request.user.id} 被锁定，阻止写入操作: {request.method} {path}")
                return self._locked_response(request, is_read_blocked=False)

        return self.get_response(request)

    def _is_allowed_path(self, path):
        """检查路径是否在允许列表中"""
        # 精确匹配
        path_stripped = path.rstrip('/')
        if path in self.ALLOWED_PATHS or path_stripped in self.ALLOWED_PATHS:
            return True

        # 前缀匹配
        for prefix in self.ALLOWED_PATH_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def _is_write_method_whitelisted(self, method, path):
        """
        检查是否是写入操作白名单中的方法
        这是为了防止 Zombie Session 的安全隐患
        """
        path_stripped = path.rstrip('/')

        for whitelisted_method, whitelisted_path in self.WRITE_METHOD_WHITELIST:
            # 精确匹配
            if (method == whitelisted_method and
                (path == whitelisted_path or path_stripped == whitelisted_path)):
                return True

        return False

    def _is_sensitive_data_path(self, path):
        """检查是否是敏感数据路径"""
        # 精确匹配
        path_stripped = path.rstrip('/')
        if path in self.SENSITIVE_DATA_PATHS or path_stripped in self.SENSITIVE_DATA_PATHS:
            return True

        # 前缀匹配
        for prefix in self.SENSITIVE_DATA_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    def _is_user_locked(self, user_id):
        """
        检查用户是否被锁定（三级检查）

        检查顺序：
        1. 用户级冻结 (vault_user_lock) - 账户全局冻结
        2. 设备级锁定 (vault_lock) - 当前设备锁定
        """
        from django.core.cache import cache
        import time

        current_time = int(time.time())

        # 1. 检查用户级冻结（账户全局）
        user_lock_key = f'vault_user_lock:{user_id}'
        user_lock_expire = cache.get(user_lock_key)
        if user_lock_expire and user_lock_expire > current_time:
            logger.debug(f"用户 {user_id} 账户被冻结，剩余 {user_lock_expire - current_time} 秒")
            return True

        # 2. 检查设备级锁定
        device_lock_key = f'vault_lock:{user_id}'
        device_lock_expire = cache.get(device_lock_key)
        if device_lock_expire and device_lock_expire > current_time:
            logger.debug(f"用户 {user_id} 设备被锁定，剩余 {device_lock_expire - current_time} 秒")
            return True

        return False

    def _is_api_request(self, request):
        """判断是否是 API 请求"""
        # 检查路径是否以 /api/ 开头
        if request.path.startswith('/api/'):
            return True

        # 检查 Accept 头是否请求 JSON
        accept = request.headers.get('Accept', '')
        if 'application/json' in accept:
            return True

        # 检查 X-Requested-With 头（AJAX 请求）
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True

        # 检查 Content-Type 是否是 JSON
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return True

        return False

    def _locked_response(self, request, is_read_blocked=False):
        """返回锁定状态响应"""
        if is_read_blocked:
            message = '您的账户因多次验证失败已被临时锁定。为保护您的数据安全，当前无法访问笔记内容。请通过重置密码解除锁定。'
        else:
            message = '您的账户因多次验证失败已被临时锁定，当前只能进行只读操作。请通过重置密码解除锁定。'

        # 如果是 API 请求，返回 JSON
        if self._is_api_request(request):
            return JsonResponse({
                'status': 'vault_locked',
                'code': 'vault_locked',
                'message': message,
                'action': 'reset_password',
                'reset_url': '/forgot-password/',
                'read_blocked': is_read_blocked
            }, status=403)

        # 如果是页面请求，返回美化的 HTML 页面
        try:
            html_content = render_to_string('vault_locked.html', {
                'message': message,
                'is_read_blocked': is_read_blocked,
                'reset_url': '/forgot-password/',
            })
            return HttpResponse(html_content, status=403, content_type='text/html')
        except Exception as e:
            logger.error(f"渲染锁定页面失败: {e}")
            # 如果模板渲染失败，返回简单的 HTML
            return HttpResponse(self._get_fallback_html(message), status=403, content_type='text/html')

    def _get_fallback_html(self, message):
        """备用的简单 HTML 页面"""
        return f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>账户已锁定</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            max-width: 500px;
        }}
        h1 {{
            color: #f56c6c;
            margin-bottom: 20px;
        }}
        p {{
            color: rgba(255,255,255,0.8);
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        a {{
            display: inline-block;
            padding: 14px 32px;
            background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
        }}
        a:hover {{
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 账户已锁定</h1>
        <p>{message}</p>
        <a href="/forgot-password/">重置密码解除锁定</a>
    </div>
</body>
</html>
'''
