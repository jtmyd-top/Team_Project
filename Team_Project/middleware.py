"""
Django middleware for IP bans, CSP, session timeout, and vault lock protection.
"""

import logging
import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect

from knowledge_project.utils.request_utils import get_client_ip


logger = logging.getLogger(__name__)


class IPBanMiddleware:
    EXEMPT_PREFIXES = [
        '/static/',
        '/forgot-password/',
        '/api/forgot-password/',
        '/api/reset-password/',
        '/reset-password/',
        '/captcha/',
        '/healthz',
        '/readyz',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("IPBanMiddleware initialized")

    def __call__(self, request):
        ip = get_client_ip(request)

        for prefix in self.EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return self.get_response(request)

        if ip and cache.get(f'banned_ip:{ip}'):
            logger.warning("Blocked banned IP %s for path %s", ip, request.path)
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


class ContentSecurityPolicyMiddleware:
    AUTH_PATHS = ['/login', '/signup', '/forgot-password', '/reset-password']

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("ContentSecurityPolicyMiddleware initialized")

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path.rstrip('/')
        is_auth_page = any(path == auth_path or path.startswith(auth_path + '/') for auth_path in self.AUTH_PATHS)
        if is_auth_page:
            return response

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
    STARTED_AT_KEY = 'auth_started_at'
    LAST_ACTIVITY_KEY = 'last_activity_at'
    EXEMPT_PREFIXES = (
        '/static/',
        '/uploads/',
        '/media/',
        '/captcha/',
        '/healthz',
        '/readyz',
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.idle_timeout = int(getattr(settings, 'SESSION_IDLE_TIMEOUT', settings.SESSION_COOKIE_AGE))
        self.absolute_timeout = int(getattr(settings, 'SESSION_ABSOLUTE_TIMEOUT', settings.SESSION_COOKIE_AGE))
        self.touch_interval = int(getattr(settings, 'SESSION_TOUCH_INTERVAL_SECONDS', 300))

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
        started_at = self._session_int(request, self.STARTED_AT_KEY)
        last_activity_at = self._session_int(request, self.LAST_ACTIVITY_KEY)
        fallback_activity_at = last_activity_at if last_activity_at is not None else started_at

        if started_at is None:
            self._initialize_metadata(request, now)
            return None

        if self.absolute_timeout > 0 and now - started_at > self.absolute_timeout:
            return self._expire(request, 'absolute_timeout')

        if self.idle_timeout > 0 and fallback_activity_at is not None and now - fallback_activity_at > self.idle_timeout:
            return self._expire(request, 'idle_timeout')

        return None

    def _session_int(self, request, key):
        value = request.session.get(key)
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _touch(self, request):
        now = int(time.time())
        last_activity_at = self._session_int(request, self.LAST_ACTIVITY_KEY)
        if (
            last_activity_at is not None
            and self.touch_interval > 0
            and now - last_activity_at < self.touch_interval
        ):
            return
        request.session[self.LAST_ACTIVITY_KEY] = now
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)

    def _initialize_metadata(self, request, now):
        request.session[self.STARTED_AT_KEY] = now
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
        '/healthz',
        '/readyz',
    ]

    WRITE_METHOD_WHITELIST = [
        ('POST', '/logout'),
        ('POST', '/api/logout/'),
        ('POST', '/forgot-password/'),
        ('POST', '/api/password-reset/'),
        ('POST', '/api/2fa/resend-email/'),
        ('GET', '/api/password-reset/'),
    ]

    SAFE_PREFIXES = (
        '/static/',
        '/captcha/',
        '/admin/',
        '/healthz',
        '/readyz',
        '/protected_uploads/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        if any(request.path.startswith(prefix) for prefix in self.SAFE_PREFIXES):
            return self.get_response(request)

        from knowledge_project.decorators import check_vault_locked

        is_locked, _, _ = check_vault_locked(request.user.id, request)
        if not is_locked:
            return self.get_response(request)

        normalized_path = request.path.rstrip('/') or '/'
        for allowed_path in self.ALLOWED_PATHS:
            allowed_normalized = allowed_path.rstrip('/') or '/'
            if normalized_path == allowed_normalized:
                return self.get_response(request)

        for method, allowed_path in self.WRITE_METHOD_WHITELIST:
            allowed_normalized = allowed_path.rstrip('/') or '/'
            if request.method == method and normalized_path == allowed_normalized:
                return self.get_response(request)

        if request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'status': 'vault_locked',
                'code': 'vault_locked',
                'message': '保密柜已锁定，请先完成验证。',
            }, status=423)

        return redirect('home')
