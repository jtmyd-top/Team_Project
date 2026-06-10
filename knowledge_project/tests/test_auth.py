"""auth 子包测试

覆盖:
- 注册流程 (SignUpView)
- 登录流程 (login_api)
- 2FA 流程 (verify_2fa_login - backup code / 缺会话保护)
- 密码修改 / 密码重置
- 用户名 / 邮箱可用性检查
- 限流辅助函数

说明:
- settings_test 使用 signed_cookies session,没有 session_key,
  所以 email 2FA 验证的完整流程(依赖 cache+session_key)在测试套件里无法 e2e 跑通。
  email 2FA 的存储侧已在 test_security_fixes.py 覆盖。
"""

from __future__ import annotations

import hashlib
import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from knowledge_project.models import PasswordResetAttempt
from knowledge_project.views.auth.rate_limit import (
    check_rate_limit,
    get_client_fingerprint,
)

from ._helpers import login, make_user, parse, post_json


# 用 db session(而不是 settings_test 默认的 signed_cookies),
# 让 Test Client 在测试中能手动 set session 字段并持久化 ——
# signed_cookies 后端的 SessionStore.save() 是 no-op,改了不会反映到 cookies。
@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _AuthTestBase(TestCase):
    """每个用例前清掉 LocMem cache,避免限流计数跨 case 串扰。"""

    def setUp(self):
        cache.clear()


# =========================================================================
# 注册
# =========================================================================
class SignupTests(_AuthTestBase):
    def _seed_email_verification(self, email: str, code: str = '123456') -> None:
        session = self.client.session
        session['registration_verification'] = {
            'email': email,
            'code': code,
            'turnstile_verified': True,
            'timestamp': time.time(),
            'purpose': 'register',
        }
        session.save()

    @patch('knowledge_project.views.auth.signup.save_user_avatar', return_value=(None, 'default'))
    def test_signup_success(self, _mocked):
        self._seed_email_verification('newbie@example.com')
        response = post_json(self.client, reverse('signup'), {
            'email': 'newbie@example.com',
            'email_code': '123456',
            'username': 'newbie01',
            'password': 'GoodPassw0rd!',
            'confirm_password': 'GoodPassw0rd!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse(response)['status'], 'success')
        self.assertTrue(User.objects.filter(username='newbie01').exists())

    def test_signup_rejects_wrong_email_code(self):
        self._seed_email_verification('wrongcode@example.com', code='000000')
        response = post_json(self.client, reverse('signup'), {
            'email': 'wrongcode@example.com',
            'email_code': '999999',
            'username': 'newbie02',
            'password': 'GoodPassw0rd!',
            'confirm_password': 'GoodPassw0rd!',
            'turnstile_token': 'dummy',  # 走完 captcha 才能到 emailCode 检查
        })
        self.assertEqual(response.status_code, 400)
        body = parse(response)
        self.assertEqual(body.get('status'), 'error')
        self.assertIn('emailCode', body.get('errors', {}))

    @patch('knowledge_project.views.auth.signup.save_user_avatar', return_value=(None, 'default'))
    def test_signup_rejects_duplicate_username(self, _mocked):
        existing = make_user('takenab')
        self._seed_email_verification('other@example.com')
        response = post_json(self.client, reverse('signup'), {
            'email': 'other@example.com',
            'email_code': '123456',
            'username': existing.username,
            'password': 'GoodPassw0rd!',
            'confirm_password': 'GoodPassw0rd!',
        })
        self.assertEqual(response.status_code, 400)

    def test_signup_requires_email_verification_in_session(self):
        response = post_json(self.client, reverse('signup'), {
            'email': 'forgot@example.com',
            'email_code': '123456',
            'username': 'forgot01',
            'password': 'GoodPassw0rd!',
            'confirm_password': 'GoodPassw0rd!',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 400)


# =========================================================================
# 登录(login_api)
# =========================================================================
class LoginApiTests(_AuthTestBase):
    @patch('knowledge_project.views.auth.login.CustomLoginView.send_login_notification', return_value=None)
    def test_login_success_without_2fa(self, _mocked):
        user = make_user('login01')
        response = post_json(self.client, reverse('login_api'), {
            'username': user.username,
            'password': 'pass-word-123!',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 200)
        session_cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        self.assertIsNotNone(session_cookie)
        self.assertEqual(int(session_cookie['max-age']), settings.SESSION_COOKIE_AGE)

    def test_login_wrong_password_returns_400(self):
        user = make_user('login02')
        response = post_json(self.client, reverse('login_api'), {
            'username': user.username,
            'password': 'WRONG',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 400)

    def test_login_requires_captcha(self):
        # 不传 turnstile_token,即使其它字段对也应被验证码挡下
        response = post_json(self.client, reverse('login_api'), {
            'username': 'anyuser',
            'password': 'anypass',
        })
        self.assertEqual(response.status_code, 400)

    @patch('knowledge_project.views.auth.login.send_mail', return_value=1)
    def test_login_2fa_email_user_returns_require_2fa(self, _mock_send):
        user = make_user('login03')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'email'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        response = post_json(self.client, reverse('login_api'), {
            'username': user.username,
            'password': 'pass-word-123!',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertTrue(body.get('require_2fa'))
        self.assertEqual(body.get('two_fa_method'), 'email')

    def test_login_banned_ip_returns_403(self):
        user = make_user('login04')
        # Django Test Client 默认走 127.0.0.1
        cache.set('banned_ip:127.0.0.1', {'reason': 'test'}, timeout=60)
        response = post_json(self.client, reverse('login_api'), {
            'username': user.username,
            'password': 'pass-word-123!',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 403)


# =========================================================================
# 2FA 登录验证(只测不依赖 session_key 的路径)
# =========================================================================
class Verify2FALoginTests(_AuthTestBase):
    def _seed_pending_2fa(self, user, method='totp'):
        session = self.client.session
        session['pending_2fa_user_id'] = user.id
        session['pending_2fa_method'] = method
        session.save()

    @patch('knowledge_project.views.auth.two_factor.CustomLoginView.send_login_notification', return_value=None)
    def test_verify_2fa_login_consumes_backup_code(self, _m):
        user = make_user('twofa01')
        backup_plain = 'BACKUP01'
        backup_hash = hashlib.sha256(backup_plain.encode()).hexdigest()
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.backup_codes = [backup_hash]
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method', 'backup_codes'])
        self._seed_pending_2fa(user, method='totp')

        response = post_json(self.client, reverse('verify_2fa_login'), {
            'code': backup_plain,
            'use_backup': True,
        })
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        # 备用码消费后,该 hash 应被移除
        self.assertNotIn(backup_hash, user.profile.backup_codes)

    def test_verify_2fa_login_rejects_invalid_backup_code(self):
        user = make_user('twofa02')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.backup_codes = [hashlib.sha256(b'GOODCODE').hexdigest()]
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method', 'backup_codes'])
        self._seed_pending_2fa(user, method='totp')

        response = post_json(self.client, reverse('verify_2fa_login'), {
            'code': 'BADCODE',
            'use_backup': True,
        })
        self.assertEqual(response.status_code, 400)

    def test_verify_2fa_login_requires_pending_session(self):
        response = post_json(self.client, reverse('verify_2fa_login'), {'code': '123456'})
        self.assertEqual(response.status_code, 400)
        body = parse(response)
        self.assertIn('过期', body.get('error', ''))


# =========================================================================
# 密码修改
# =========================================================================
class PasswordChangeTests(_AuthTestBase):
    def test_change_password_wrong_current_returns_400(self):
        user = make_user('changer01')
        login(self.client, user)
        response = post_json(self.client, reverse('change_password'), {
            'current_password': 'WRONG',
            'new_password': 'NewPass1234!',
            'confirm_password': 'NewPass1234!',
        })
        self.assertEqual(response.status_code, 400)

    def test_change_password_mismatched_new_returns_400(self):
        user = make_user('changer02')
        login(self.client, user)
        response = post_json(self.client, reverse('change_password'), {
            'current_password': 'pass-word-123!',
            'new_password': 'NewPass1234!',
            'confirm_password': 'OtherPass1234!',
        })
        self.assertEqual(response.status_code, 400)

    def test_change_password_rejects_short_new_password(self):
        user = make_user('changer03')
        login(self.client, user)
        response = post_json(self.client, reverse('change_password'), {
            'current_password': 'pass-word-123!',
            'new_password': 'Short1',
            'confirm_password': 'Short1',
        })
        self.assertEqual(response.status_code, 400)

    def test_change_password_success(self):
        user = make_user('changer04')
        login(self.client, user)
        response = post_json(self.client, reverse('change_password'), {
            'current_password': 'pass-word-123!',
            'new_password': 'NewPass1234!',
            'confirm_password': 'NewPass1234!',
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewPass1234!'))


# =========================================================================
# 密码重置
# =========================================================================
class PasswordResetTests(_AuthTestBase):
    def test_password_reset_api_does_not_leak_user_existence(self):
        response = post_json(self.client, reverse('password_reset_api'), {
            'email': 'nonexistent@example.com',
            'turnstile_token': 'dummy',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse(response)['status'], 'success')

    def test_password_reset_api_returns_success_for_existing_user(self):
        user = make_user('reset01')
        with patch('knowledge_project.views.auth.password_reset.threading.Thread'):
            response = post_json(self.client, reverse('password_reset_api'), {
                'email': user.email,
                'turnstile_token': 'dummy',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(parse(response)['status'], 'success')

    def test_reset_password_view_rejects_invalid_token(self):
        user = make_user('reset02')
        response = self.client.get(reverse('reset_password', args=[user.id, 'invalid-token']))
        self.assertEqual(response.status_code, 200)
        # 模板由 Vue 客户端渲染,不能从 HTML 文本判断;改查 context
        self.assertFalse(response.context['validlink'])

    def test_reset_password_view_succeeds_with_valid_token(self):
        user = make_user('reset03')
        token = PasswordResetTokenGenerator().make_token(user)
        response = self.client.post(
            reverse('reset_password', args=[user.id, token]),
            data={'password': 'NewPass1234!', 'confirm_password': 'NewPass1234!'},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewPass1234!'))


# =========================================================================
# 用户名 / 邮箱可用性检查
# =========================================================================
class CheckUsernameTests(_AuthTestBase):
    def test_check_username_taken(self):
        user = make_user('takenuser')
        response = self.client.get(reverse('check_username') + f'?username={user.username}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(parse(response)['is_taken'])

    def test_check_username_invalid_format(self):
        # 大写开头不符合 USERNAME_REGEX
        response = self.client.get(reverse('check_username') + '?username=BadName')
        body = parse(response)
        self.assertTrue(body['is_taken'])
        self.assertIn('用户名', body['message'])

    def test_check_username_available(self):
        response = self.client.get(reverse('check_username') + '?username=goodone')
        self.assertFalse(parse(response)['is_taken'])

    def test_check_username_requires_param(self):
        response = self.client.get(reverse('check_username'))
        self.assertEqual(response.status_code, 400)


class CheckEmailTests(_AuthTestBase):
    def test_check_email_taken(self):
        user = make_user('emailcheck01')
        response = self.client.get(reverse('check_email') + f'?email={user.email}')
        self.assertTrue(parse(response)['is_taken'])

    def test_check_email_available(self):
        response = self.client.get(reverse('check_email') + '?email=notyet@example.com')
        self.assertFalse(parse(response)['is_taken'])

    def test_check_email_rejects_invalid_format(self):
        response = self.client.get(reverse('check_email') + '?email=not-an-email')
        body = parse(response)
        self.assertTrue(body['is_taken'])
        self.assertIn('格式', body['message'])


# =========================================================================
# 限流辅助函数
# =========================================================================
class RateLimitHelperTests(_AuthTestBase):
    factory = RequestFactory()

    def test_client_fingerprint_is_stable(self):
        req1 = self.factory.get('/', HTTP_USER_AGENT='Mozilla', HTTP_ACCEPT_LANGUAGE='en')
        req2 = self.factory.get('/', HTTP_USER_AGENT='Mozilla', HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(get_client_fingerprint(req1), get_client_fingerprint(req2))

    def test_client_fingerprint_changes_with_user_agent(self):
        req1 = self.factory.get('/', HTTP_USER_AGENT='Mozilla')
        req2 = self.factory.get('/', HTTP_USER_AGENT='Chrome')
        self.assertNotEqual(get_client_fingerprint(req1), get_client_fingerprint(req2))

    def test_check_rate_limit_allows_first_request(self):
        ok, _ = check_rate_limit('first@example.com', '1.2.3.4', 'fp', limit=3)
        self.assertTrue(ok)

    def test_check_rate_limit_blocks_after_email_threshold(self):
        for _ in range(3):
            PasswordResetAttempt.objects.create(
                email='spam@example.com',
                ip_address='1.2.3.4',
                fingerprint='fp',
                user_agent='ua',
                is_successful=False,
            )
        ok, msg = check_rate_limit('spam@example.com', '9.9.9.9', 'other-fp', limit=3)
        self.assertFalse(ok)
        self.assertIn('上限', msg)
