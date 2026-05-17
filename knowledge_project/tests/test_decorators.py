"""decorators 模块测试

覆盖:
- verify_backup_code_secure: 恒定时间 + 原子消费
- verify_totp_with_replay_protection: 重放保护
- verify_email_code_from_cache: 验证码错 / 过期
- send_operation_2fa_email: 频率限制(每小时 3 次,每天 5 次)
- verify_2fa_for_request: 综合流程 + 失败计数锁定
- check_and_ban_ip: 24h 内失败 ≥ 10 次自动 ban
- get_request_data / get_param
"""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pyotp
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from knowledge_project.decorators import (
    IP_FAIL_THRESHOLD,
    check_and_ban_ip,
    get_param,
    get_request_data,
    send_operation_2fa_email,
    verify_2fa_for_request,
    verify_backup_code_secure,
    verify_email_code_from_cache,
    verify_totp_with_replay_protection,
)
from knowledge_project.models import AccessLog, Profile

from ._helpers import make_user


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _DecoratorsTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# verify_backup_code_secure
# =========================================================================
class VerifyBackupCodeTests(_DecoratorsTestBase):
    def test_valid_backup_code_is_consumed(self):
        user = make_user('bc01')
        plain = 'BACKUPCODE1234'
        user.profile.backup_codes = [hashlib.sha256(plain.encode()).hexdigest()]
        user.profile.save(update_fields=['backup_codes'])

        self.assertTrue(verify_backup_code_secure(user.profile, plain))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.backup_codes, [])

    def test_invalid_backup_code_returns_false(self):
        user = make_user('bc02')
        user.profile.backup_codes = [hashlib.sha256(b'GOOD').hexdigest()]
        user.profile.save(update_fields=['backup_codes'])
        self.assertFalse(verify_backup_code_secure(user.profile, 'BAD'))
        user.profile.refresh_from_db()
        # 失败时不应消耗 backup_codes
        self.assertEqual(len(user.profile.backup_codes), 1)

    def test_empty_backup_codes_returns_false(self):
        user = make_user('bc03')
        user.profile.backup_codes = []
        user.profile.save(update_fields=['backup_codes'])
        self.assertFalse(verify_backup_code_secure(user.profile, 'ANY'))


# =========================================================================
# verify_totp_with_replay_protection
# =========================================================================
class VerifyTotpTests(_DecoratorsTestBase):
    def test_valid_code_passes(self):
        user = make_user('totp01')
        secret = pyotp.random_base32()
        user.profile.totp_secret = secret
        user.profile.save(update_fields=['totp_secret'])

        code = pyotp.TOTP(secret).now()
        success, msg = verify_totp_with_replay_protection(user.profile, code)
        self.assertTrue(success, msg)

    def test_replay_is_rejected(self):
        user = make_user('totp02')
        secret = pyotp.random_base32()
        user.profile.totp_secret = secret
        user.profile.save(update_fields=['totp_secret'])

        code = pyotp.TOTP(secret).now()
        # 第一次成功
        ok1, _ = verify_totp_with_replay_protection(user.profile, code)
        # 第二次用同样的码 → 拒绝
        ok2, msg2 = verify_totp_with_replay_protection(user.profile, code)
        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertIn('已被使用', msg2)

    def test_wrong_code_returns_false(self):
        user = make_user('totp03')
        user.profile.totp_secret = pyotp.random_base32()
        user.profile.save(update_fields=['totp_secret'])
        success, msg = verify_totp_with_replay_protection(user.profile, '000000')
        self.assertFalse(success)
        self.assertIn('错误', msg)

    def test_missing_secret_returns_false(self):
        user = make_user('totp04')
        success, msg = verify_totp_with_replay_protection(user.profile, '123456')
        self.assertFalse(success)


# =========================================================================
# verify_email_code_from_cache
# =========================================================================
class VerifyEmailCodeTests(_DecoratorsTestBase):
    def test_correct_code_passes_and_consumes(self):
        user_id = 42
        cache.set(f'op2fa:{user_id}', '123456', timeout=300)
        ok, _ = verify_email_code_from_cache(user_id, '123456')
        self.assertTrue(ok)
        # 一次性消费
        self.assertIsNone(cache.get(f'op2fa:{user_id}'))

    def test_wrong_code_returns_false(self):
        user_id = 43
        cache.set(f'op2fa:{user_id}', '111111', timeout=300)
        ok, msg = verify_email_code_from_cache(user_id, '999999')
        self.assertFalse(ok)
        self.assertIn('错误', msg)
        # 失败不消耗 cache
        self.assertEqual(cache.get(f'op2fa:{user_id}'), '111111')

    def test_missing_code_returns_false(self):
        ok, msg = verify_email_code_from_cache(44, '123456')
        self.assertFalse(ok)
        self.assertIn('过期', msg)


# =========================================================================
# send_operation_2fa_email - 频率限制
# =========================================================================
class SendOpEmailRateLimitTests(_DecoratorsTestBase):
    """settings_test 用 locmem email backend,send_mail 不会真发邮件,
    会写到 mail.outbox。"""

    def setUp(self):
        super().setUp()
        mail.outbox = []

    def test_hourly_limit_blocks_after_3(self):
        user = make_user('se01')
        cache.set(f'email_code_hourly_general_2fa_user_{user.id}', 3, timeout=3600)
        ok, msg = send_operation_2fa_email(user, operation_type='general')
        self.assertFalse(ok)
        self.assertIn('上限', msg)
        self.assertEqual(len(mail.outbox), 0)

    def test_daily_limit_blocks_after_5(self):
        user = make_user('se02')
        cache.set(f'email_code_daily_general_2fa_user_{user.id}', 5, timeout=86400)
        ok, msg = send_operation_2fa_email(user, operation_type='general')
        self.assertFalse(ok)
        self.assertIn('上限', msg)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_lock_prevents_rapid_resend(self):
        user = make_user('se03')
        cache.set(f'op2fa_send_lock:{user.id}:general', True, timeout=90)
        # 发送锁存在时返回 True 但不实际发邮件
        ok, _ = send_operation_2fa_email(user, operation_type='general')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 0)

    def test_first_send_writes_code_to_cache(self):
        user = make_user('se04')
        ok, _ = send_operation_2fa_email(user, operation_type='password_change')
        self.assertTrue(ok)
        self.assertIsNotNone(cache.get(f'op2fa:{user.id}'))
        # 邮件已发送到 locmem outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)


# =========================================================================
# verify_2fa_for_request
# =========================================================================
class Verify2FAForRequestTests(_DecoratorsTestBase):
    factory = RequestFactory()

    def _make_request(self, user):
        req = self.factory.post('/')
        req.user = user
        return req

    def test_user_without_2fa_passes_directly(self):
        user = make_user('vfr01')
        # 默认 two_fa_enabled=False
        req = self._make_request(user)
        ok, msg = verify_2fa_for_request(req, 'any-code')
        self.assertTrue(ok)

    def test_email_2fa_with_correct_code(self):
        user = make_user('vfr02')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'email'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        cache.set(f'op2fa:{user.id}', '654321', timeout=300)
        req = self._make_request(user)
        ok, _ = verify_2fa_for_request(req, '654321')
        self.assertTrue(ok)
        # 验证码消费
        self.assertIsNone(cache.get(f'op2fa:{user.id}'))

    def test_too_many_attempts_blocks(self):
        user = make_user('vfr03')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'email'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        cache.set(f'2fa_attempts:{user.id}', 10, timeout=300)
        req = self._make_request(user)
        ok, msg = verify_2fa_for_request(req, '999999')
        self.assertFalse(ok)
        self.assertIn('过多', msg)


# =========================================================================
# check_and_ban_ip
# =========================================================================
class CheckAndBanIpTests(_DecoratorsTestBase):
    def test_ban_triggered_after_threshold(self):
        ip = '203.0.113.7'
        # 制造 10 条失败记录
        for _ in range(IP_FAIL_THRESHOLD):
            AccessLog.record_vault_fail(user_identifier='attacker', ip_address=ip, details='x')
        check_and_ban_ip(ip, 'attacker')
        self.assertIsNotNone(cache.get(f'banned_ip:{ip}'))

    def test_no_ban_below_threshold(self):
        ip = '203.0.113.8'
        for _ in range(IP_FAIL_THRESHOLD - 1):
            AccessLog.record_vault_fail(user_identifier='attacker', ip_address=ip, details='x')
        check_and_ban_ip(ip, 'attacker')
        self.assertIsNone(cache.get(f'banned_ip:{ip}'))


# =========================================================================
# get_request_data / get_param
# =========================================================================
class RequestDataHelperTests(_DecoratorsTestBase):
    factory = RequestFactory()

    def test_parses_json_body(self):
        req = self.factory.post('/', data='{"foo": "bar"}', content_type='application/json')
        self.assertEqual(get_request_data(req), {'foo': 'bar'})

    def test_falls_back_to_post(self):
        req = self.factory.post('/', data={'name': 'alice'})
        data = get_request_data(req)
        self.assertIn('name', data)

    def test_get_param_unwraps_list_from_post(self):
        req = self.factory.post('/', data={'tags': 'first'})
        # POST QueryDict 返回 list
        self.assertEqual(get_param(req, 'tags'), 'first')

    def test_get_param_returns_default(self):
        req = self.factory.post('/', data='{}', content_type='application/json')
        self.assertEqual(get_param(req, 'missing', default='fallback'), 'fallback')

    def test_invalid_json_returns_empty_dict(self):
        req = self.factory.post('/', data='not json', content_type='application/json')
        self.assertEqual(get_request_data(req), {})
