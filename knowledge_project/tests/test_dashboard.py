"""dashboard 模块测试 — 只测权限边界 + ban_ip 关键路径

覆盖:
- dashboard_view: 非 superuser 重定向 / superuser 渲染
- dashboard_stats_api: 非 superuser 403 / superuser 返回数据
- ban_ip_api: 鉴权 / IP 格式校验 / 缺字段 / 成功写入 cache
- healthz / readyz: 基本响应
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from messaging.models import GroupMessage, Message, MessageGroup
from ops.models import BackupRecord

from ._helpers import login, make_user, parse, post_json


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class _DashboardTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# dashboard_view
# =========================================================================
class DashboardViewTests(_DashboardTestBase):
    def test_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_normal_user_redirected_to_home(self):
        user = make_user('dv01')
        login(self.client, user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('home'), response['Location'])

    def test_staff_without_superuser_also_redirected(self):
        # is_staff 不够,必须 is_superuser
        user = make_user('dv02', is_staff=True)
        login(self.client, user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_access(self):
        admin = make_user('dv03_admin', is_superuser=True)
        login(self.client, admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)


# =========================================================================
# dashboard_stats_api
# =========================================================================
class DashboardStatsApiTests(_DashboardTestBase):
    def test_requires_login(self):
        response = self.client.get(reverse('dashboard_stats_api'))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_normal_user_forbidden(self):
        user = make_user('ds01')
        login(self.client, user)
        response = self.client.get(reverse('dashboard_stats_api'))
        self.assertEqual(response.status_code, 403)

    def test_staff_without_superuser_forbidden(self):
        user = make_user('ds02', is_staff=True)
        login(self.client, user)
        response = self.client.get(reverse('dashboard_stats_api'))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_get_assets_section(self):
        admin = make_user('ds03_admin', is_superuser=True)
        login(self.client, admin)
        response = self.client.get(reverse('dashboard_stats_api') + '?section=assets')
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['status'], 'success')
        self.assertIn('assets', body)

    def test_superuser_can_get_operations_section(self):
        admin = make_user('ds04_admin', is_superuser=True)
        member = make_user('ds04_member')
        group = MessageGroup.objects.create(
            name='Operations group',
            owner=admin,
            created_by=admin,
        )
        Message.objects.create(sender=admin, recipient=member, content='direct activity')
        GroupMessage.objects.create(group=group, sender=admin, content='group activity')
        login(self.client, admin)

        response = self.client.get(reverse('dashboard_stats_api') + '?section=operations')

        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['operations']['active_groups'], 1)
        self.assertEqual(body['operations']['direct_messages_7d'], 1)
        self.assertEqual(body['operations']['group_messages_7d'], 1)
        self.assertIn('activity_trend', body['operations'])


# =========================================================================
# ban_ip_api
# =========================================================================
class BanIpApiTests(_DashboardTestBase):
    def test_requires_login(self):
        response = post_json(self.client, reverse('ban_ip_api'), {'ip': '1.2.3.4'})
        self.assertIn(response.status_code, (302, 401, 403))

    def test_normal_user_forbidden(self):
        user = make_user('bi01')
        login(self.client, user)
        response = post_json(self.client, reverse('ban_ip_api'), {'ip': '1.2.3.4'})
        self.assertEqual(response.status_code, 403)

    def test_staff_without_superuser_forbidden(self):
        user = make_user('bi02', is_staff=True)
        login(self.client, user)
        response = post_json(self.client, reverse('ban_ip_api'), {'ip': '1.2.3.4'})
        self.assertEqual(response.status_code, 403)

    def test_superuser_ban_ip_success(self):
        admin = make_user('bi03_admin', is_superuser=True)
        login(self.client, admin)
        response = post_json(self.client, reverse('ban_ip_api'), {
            'ip': '203.0.113.5', 'reason': '测试封禁',
        })
        self.assertEqual(response.status_code, 200)
        # 应该写到 cache
        entry = cache.get('banned_ip:203.0.113.5')
        self.assertIsNotNone(entry)
        self.assertEqual(entry['banned_by'], admin.username)
        self.assertEqual(entry['reason'], '测试封禁')

    def test_invalid_ip_format(self):
        admin = make_user('bi04_admin', is_superuser=True)
        login(self.client, admin)
        response = post_json(self.client, reverse('ban_ip_api'), {'ip': 'not-an-ip'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('格式', parse(response)['message'])

    def test_missing_ip(self):
        admin = make_user('bi05_admin', is_superuser=True)
        login(self.client, admin)
        response = post_json(self.client, reverse('ban_ip_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json(self):
        admin = make_user('bi06_admin', is_superuser=True)
        login(self.client, admin)
        response = self.client.post(
            reverse('ban_ip_api'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# =========================================================================
# healthz / readyz
# =========================================================================
class HealthCheckTests(_DashboardTestBase):
    def test_healthz_anonymous_ok(self):
        response = self.client.get(reverse('healthz'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['status'], 'ok')

    def test_readyz_anonymous_ok(self):
        # 测试环境 LocMemCache + SQLite 都正常,readyz 应该返回 200
        response = self.client.get(reverse('readyz'))
        self.assertIn(response.status_code, (200, 503))
        body = parse(response)
        self.assertIn('checks', body)

    def test_service_worker_is_available_from_origin_root(self):
        with TemporaryDirectory() as static_root:
            worker_dir = Path(static_root) / 'dist'
            worker_dir.mkdir()
            (worker_dir / 'sw.js').write_text('self.addEventListener("install", () => {});', encoding='utf-8')
            with override_settings(STATIC_ROOT=static_root):
                response = self.client.get(reverse('service_worker'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Service-Worker-Allowed'], '/')
                self.assertIn('no-cache', response['Cache-Control'])
                response.close()


class BackupCommandTests(_DashboardTestBase):
    def test_run_backup_creates_a_snapshot_record_and_archive(self):
        with TemporaryDirectory() as backup_dir:
            call_command(
                'run_backup',
                output_dir=backup_dir,
                retention_days=0,
            )

            record = BackupRecord.objects.get(kind=BackupRecord.KIND_SNAPSHOT)
            self.assertEqual(record.status, BackupRecord.STATUS_SUCCEEDED)
            self.assertTrue(Path(record.storage_path).is_file())
            self.assertGreater(record.size_bytes, 0)
