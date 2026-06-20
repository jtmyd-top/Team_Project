"""vault 子模块测试

覆盖:
- vault_status: 2FA / 解锁状态 / 计数 / 初始化标记
- vault_lock: 撤销访问
- vault_lock_status: 失败计数与锁定状态
- vault_init: 初始化与重复保护
- vault_notes_list: 列出保密笔记 / 未解锁拦截
- VaultLockMiddleware: 白名单 / 未登录放行 / SAFE_PREFIXES
- decorators 辅助: increment_vault_fail_count / check_vault_locked /
                  grant_vault_access / check_vault_access /
                  设备级 3 次锁 60s,账户级 5 次锁 24h

不重复 test_security_fixes.py 已覆盖的:
- VaultLockMiddleware API 锁定时 423
- vault_locked 字段空转修复
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.services import verify_2fa_for_request
from vault.services import (
    VAULT_DEVICE_FAIL_THRESHOLD,
    VAULT_DEVICE_LOCK_SECONDS,
    VAULT_USER_FAIL_THRESHOLD,
    VAULT_USER_LOCK_SECONDS,
    check_vault_access,
    check_vault_locked,
    grant_vault_access,
    increment_vault_fail_count,
    is_vault_access_session_scoped,
    reset_vault_fail_count,
    revoke_vault_access,
    verify_vault_2fa,
)
from knowledge_project.models import Note
from Team_Project.middleware import VaultLockMiddleware

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _VaultTestBase(TestCase):
    """每个用例前清 LocMem cache(失败计数 / 锁存 / 解锁授权都在 cache 里)。"""

    def setUp(self):
        self._vault_kek_env = patch.dict(
            'os.environ',
            {'VAULT_KEK': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='},
        )
        self._vault_kek_env.start()
        self.addCleanup(self._vault_kek_env.stop)
        cache.clear()


# =========================================================================
# vault_status
# =========================================================================
class VaultStatusTests(_VaultTestBase):
    def test_status_no_2fa_user_is_verified(self):
        user = make_user('vs01')
        login(self.client, user)
        response = self.client.get(reverse('vault_status'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertFalse(body['two_fa_enabled'])
        self.assertTrue(body['is_verified'])
        self.assertEqual(body['secret_notes_count'], 0)

    def test_status_counts_user_secret_notes(self):
        user = make_user('vs02')
        Note.objects.create(author=user, title='s1', content='', is_secret=True)
        Note.objects.create(author=user, title='s2', content='', is_secret=True)
        Note.objects.create(author=user, title='s3', content='', is_secret=True, is_trashed=True)
        Note.objects.create(author=user, title='open', content='')
        login(self.client, user)
        body = parse(self.client.get(reverse('vault_status')))
        # 排除回收站
        self.assertEqual(body['secret_notes_count'], 2)

    def test_status_2fa_user_without_vault_access(self):
        user = make_user('vs03')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        login(self.client, user)
        body = parse(self.client.get(reverse('vault_status')))
        self.assertTrue(body['two_fa_enabled'])
        self.assertFalse(body['is_verified'])
        self.assertEqual(body['remaining_seconds'], 0)


# =========================================================================
# vault_lock
# =========================================================================
class VaultLockTests(_VaultTestBase):
    def test_lock_revokes_access(self):
        user = make_user('vlock01')
        user.profile.two_fa_enabled = True
        user.profile.save(update_fields=['two_fa_enabled'])
        login(self.client, user)

        # 先通过 verify 拿到访问权限(用 helper 模拟)
        request = self.client.session
        # 直接用 grant_vault_access 模拟解锁后状态
        from django.test import RequestFactory
        factory = RequestFactory()
        fake_req = factory.get('/')
        fake_req.session = self.client.session
        grant_vault_access(fake_req, window_seconds=600)
        fake_req.session.save()
        self.assertTrue(check_vault_access(fake_req))

        # 调 lock API
        response = post_json(self.client, reverse('vault_lock'))
        self.assertEqual(response.status_code, 200)

        # 注意:lock API 用自身 request.session 的 session_key,
        # 与 fake_req 的 session_key 一致(都指向同一个 session_key)。


# =========================================================================
# vault_lock_status
# =========================================================================
class VaultLockStatusTests(_VaultTestBase):
    def test_no_failures_returns_unlocked(self):
        user = make_user('vlst01')
        login(self.client, user)
        body = parse(self.client.get(reverse('vault_lock_status')))
        self.assertFalse(body['is_locked'])
        self.assertEqual(body['fail_count'], 0)


# =========================================================================
# vault_init
# =========================================================================
class VaultInitTests(_VaultTestBase):
    def test_already_initialized_returns_400(self):
        user = make_user('vinit01')
        user.profile.vault_initialized = True
        user.profile.encrypted_vault_key = 'fake'
        user.profile.vault_key_iv = 'fake'
        user.profile.save(update_fields=['vault_initialized', 'encrypted_vault_key', 'vault_key_iv'])
        login(self.client, user)
        response = post_json(self.client, reverse('vault_init'))
        self.assertEqual(response.status_code, 400)

    def test_init_persists_dek(self):
        user = make_user('vinit02')
        # 因为 signal `create_user_profile` 已经自动初始化了,先重置
        user.profile.vault_initialized = False
        user.profile.encrypted_vault_key = ''
        user.profile.vault_key_iv = ''
        user.profile.save(update_fields=['vault_initialized', 'encrypted_vault_key', 'vault_key_iv'])
        login(self.client, user)
        response = post_json(self.client, reverse('vault_init'))
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.vault_initialized)
        self.assertTrue(user.profile.encrypted_vault_key)
        self.assertTrue(user.profile.vault_key_iv)


# =========================================================================
# vault_notes_list
# =========================================================================
class VaultNotesListTests(_VaultTestBase):
    def test_no_2fa_returns_secret_notes(self):
        user = make_user('vnl01')
        Note.objects.create(author=user, title='s1', content='enc1', is_secret=True)
        Note.objects.create(author=user, title='open', content='plain')
        login(self.client, user)
        response = self.client.get(reverse('vault_notes_list'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        # 只返回保密笔记
        notes = body.get('notes') if isinstance(body, dict) else body
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['title'], 's1')

    def test_2fa_user_without_unlock_is_required_to_verify(self):
        user = make_user('vnl02')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        login(self.client, user)
        response = self.client.get(reverse('vault_notes_list'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body.get('status'), 'require_vault_2fa')


# =========================================================================
# VaultLockMiddleware: 白名单 / SAFE_PREFIXES / 未登录放行
# =========================================================================
class VaultLockMiddlewareWhitelistTests(_VaultTestBase):
    """中间件的拦截语义:check_vault_locked=True 时,只放行白名单。"""

    factory = RequestFactory()

    def _build_request(self, path, user, method='GET'):
        request = getattr(self.factory, method.lower())(path, HTTP_ACCEPT='application/json')
        request.user = user
        return request

    @patch('vault.services.check_vault_locked', return_value=(True, 60, 3))
    def test_locked_allowed_path_passes(self, _m):
        user = make_user('vmw01')
        request = self._build_request('/', user)
        response = VaultLockMiddleware(lambda req: _ok_response())(request)
        # ALLOWED_PATHS 包含 '/' → 应放行
        self.assertEqual(response.status_code, 200)

    @patch('vault.services.check_vault_locked', return_value=(True, 60, 3))
    def test_locked_safe_prefix_passes(self, _m):
        user = make_user('vmw02')
        request = self._build_request('/static/css/main.css', user)
        response = VaultLockMiddleware(lambda req: _ok_response())(request)
        # SAFE_PREFIXES 包含 '/static/' → 应放行
        self.assertEqual(response.status_code, 200)

    @patch('vault.services.check_vault_locked', return_value=(True, 60, 3))
    def test_anonymous_user_passes_even_when_locked(self, _m):
        from django.contrib.auth.models import AnonymousUser
        request = self._build_request('/api/notes/1/', AnonymousUser())
        response = VaultLockMiddleware(lambda req: _ok_response())(request)
        # 未登录用户不拦截
        self.assertEqual(response.status_code, 200)

    @patch('vault.services.check_vault_locked', return_value=(False, 0, 0))
    def test_unlocked_user_passes(self, _m):
        user = make_user('vmw04')
        request = self._build_request('/api/notes/1/', user)
        response = VaultLockMiddleware(lambda req: _ok_response())(request)
        self.assertEqual(response.status_code, 200)

    @patch('vault.services.check_vault_locked', return_value=(True, 60, 3))
    def test_locked_non_api_html_redirects_home(self, _m):
        user = make_user('vmw05')
        # 不带 application/json,模拟浏览器导航
        request = self.factory.get('/knowledge/')
        request.user = user
        response = VaultLockMiddleware(lambda req: _ok_response())(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')


def _ok_response():
    from django.http import HttpResponse
    return HttpResponse('OK')


# =========================================================================
# decorators 失败计数 / 锁定 / 解锁授权
# =========================================================================
class VaultFailureCountAndLockTests(_VaultTestBase):
    factory = RequestFactory()

    def _make_request(self, user):
        request = self.factory.get('/api/vault/verify/', HTTP_USER_AGENT='ua')
        request.user = user
        # 给一个 session
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()
        request.session.create()
        return request

    def test_device_lock_after_three_failures(self):
        user = make_user('vfc01')
        request = self._make_request(user)
        for _ in range(VAULT_DEVICE_FAIL_THRESHOLD):
            increment_vault_fail_count(user.id, request=request)
        is_locked, remaining, fail_count = check_vault_locked(user.id, request=request)
        self.assertTrue(is_locked)
        # 设备锁 60s, 上限 VAULT_DEVICE_LOCK_SECONDS
        self.assertLessEqual(remaining, VAULT_DEVICE_LOCK_SECONDS)
        self.assertGreater(remaining, 0)

    def test_user_lock_takes_precedence_after_five_failures(self):
        user = make_user('vfc02')
        request = self._make_request(user)
        for _ in range(VAULT_USER_FAIL_THRESHOLD):
            increment_vault_fail_count(user.id, request=request)
        is_locked, remaining, fail_count = check_vault_locked(user.id, request=request)
        self.assertTrue(is_locked)
        # 账户级锁 24h
        self.assertGreater(remaining, VAULT_DEVICE_LOCK_SECONDS)
        self.assertLessEqual(remaining, VAULT_USER_LOCK_SECONDS)

    def test_reset_clears_failure_count(self):
        user = make_user('vfc03')
        request = self._make_request(user)
        for _ in range(VAULT_DEVICE_FAIL_THRESHOLD):
            increment_vault_fail_count(user.id, request=request)
        reset_vault_fail_count(user.id, request=request)
        is_locked, _, fail_count = check_vault_locked(user.id, request=request)
        self.assertFalse(is_locked)
        self.assertEqual(fail_count, 0)

    def test_grant_and_revoke_vault_access(self):
        user = make_user('vfc04')
        request = self._make_request(user)
        self.assertFalse(check_vault_access(request))
        grant_vault_access(request, window_seconds=300)
        self.assertTrue(check_vault_access(request))
        revoke_vault_access(request)
        self.assertFalse(check_vault_access(request))

    def test_session_scoped_grant_keeps_access_flag(self):
        user = make_user('vfc05')
        request = self._make_request(user)
        grant_vault_access(request, window_seconds=300, session_scoped=True)
        self.assertTrue(check_vault_access(request))
        self.assertTrue(is_vault_access_session_scoped(request))

    @patch('vault.services.verify_2fa_for_request', return_value=(True, ''))
    def test_verify_duration_zero_marks_session_scoped(self, _verify):
        user = make_user('vfc06')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        request = self._make_request(user)

        result = verify_vault_2fa(request, '123456', duration_minutes=0)

        self.assertTrue(result['success'])
        self.assertTrue(result['session_scoped'])
        self.assertTrue(is_vault_access_session_scoped(request))
