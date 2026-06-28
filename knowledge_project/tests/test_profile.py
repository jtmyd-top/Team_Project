"""profile 模块测试

覆盖:
- update_profile: 更新昵称 / 更新 bio / 重复用户名 / 无效格式 / bio 过长 / 无字段 / JSON 错误
- update_email: 密码错误 / 验证码错 / 缺参数 / 邮箱占用 / 2FA 触发 / 成功
- toggle_profile_like: 点赞 / 取消点赞 / 计数同步
- notification_preferences: GET / POST 单字段 / POST 邮件+浏览器 / JSON 错误
- theme_settings: GET / POST 主题 / 布局 / 兼容 primaryColor / JSON 错误
- user_public_profile_view: 渲染 / is_self / is_following / 404
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    LoginDevice,
    Profile,
    ProfileLike,
    ProfileVisit,
    SecurityAuditLog,
)
from messaging.models import (
    MessageGroup,
    MessageGroupMember,
    MessagePreference,
    UserBlocklist,
    UserFollow,
)
from notes.models import Note
from notifications.models import UserNotification

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _ProfileTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# update_profile
# =========================================================================
class UpdateProfileTests(_ProfileTestBase):
    def test_update_nickname_success(self):
        user = make_user('up01_init')
        login(self.client, user)
        response = post_json(self.client, reverse('update_profile'), {'nickname': 'newname01'})
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, 'newname01')

    def test_update_bio_success(self):
        user = make_user('up02')
        login(self.client, user)
        response = post_json(self.client, reverse('update_profile'), {'bio': '我的签名'})
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.bio, '我的签名')

    def test_update_nickname_invalid_format(self):
        user = make_user('up03')
        login(self.client, user)
        # 大写开头不匹配 USERNAME_REGEX
        response = post_json(self.client, reverse('update_profile'), {'nickname': 'BadName'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('用户名', parse(response)['message'])

    def test_update_nickname_too_short(self):
        user = make_user('up04')
        login(self.client, user)
        # 少于 6 字符
        response = post_json(self.client, reverse('update_profile'), {'nickname': 'abc'})
        self.assertEqual(response.status_code, 400)

    def test_update_nickname_taken(self):
        a = make_user('up05_a')
        b = make_user('up05_taken_user')
        login(self.client, a)
        response = post_json(self.client, reverse('update_profile'), {'nickname': b.username})
        self.assertEqual(response.status_code, 400)
        self.assertIn('占用', parse(response)['message'])

    def test_update_bio_too_long(self):
        user = make_user('up06')
        login(self.client, user)
        response = post_json(self.client, reverse('update_profile'), {'bio': 'x' * 161})
        self.assertEqual(response.status_code, 400)

    def test_update_with_empty_payload(self):
        user = make_user('up07')
        login(self.client, user)
        response = post_json(self.client, reverse('update_profile'), {})
        # 没有任何字段需要更新 -> 400
        self.assertEqual(response.status_code, 400)

    def test_update_invalid_json(self):
        user = make_user('up08')
        login(self.client, user)
        response = self.client.post(
            reverse('update_profile'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_update_requires_login(self):
        response = post_json(self.client, reverse('update_profile'), {'bio': 'x'})
        self.assertIn(response.status_code, (302, 401, 403))


# =========================================================================
# update_email
# =========================================================================
class UpdateEmailTests(_ProfileTestBase):
    def _seed_email_change_verification(self, email: str, code: str = '123456'):
        session = self.client.session
        session['email_change_verification'] = {'email': email, 'code': code}
        session.save()

    def test_missing_params(self):
        user = make_user('ue01')
        login(self.client, user)
        response = post_json(self.client, reverse('update_email'), {})
        self.assertEqual(response.status_code, 400)

    def test_wrong_current_password(self):
        user = make_user('ue02')
        login(self.client, user)
        self._seed_email_change_verification('new@example.com')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'WRONG',
            'new_email': 'new@example.com',
            'code': '123456',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('密码', parse(response)['message'])

    def test_wrong_code(self):
        user = make_user('ue03')
        login(self.client, user)
        self._seed_email_change_verification('new@example.com', code='000000')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'pass-word-123!',
            'new_email': 'new@example.com',
            'code': '999999',
        })
        self.assertEqual(response.status_code, 400)

    def test_email_already_taken(self):
        user = make_user('ue04')
        make_user('ue04_other', email='taken@example.com')
        login(self.client, user)
        self._seed_email_change_verification('taken@example.com')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'pass-word-123!',
            'new_email': 'taken@example.com',
            'code': '123456',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('绑定', parse(response)['message'])

    def test_2fa_required_returns_require_2fa(self):
        user = make_user('ue05')
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])
        login(self.client, user)
        self._seed_email_change_verification('new@example.com')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'pass-word-123!',
            'new_email': 'new@example.com',
            'code': '123456',
        })
        # 没传 two_fa_code -> 返回 require_2fa(200)
        body = parse(response)
        self.assertEqual(body.get('status'), 'require_2fa')

    def test_update_email_success(self):
        user = make_user('ue06')
        login(self.client, user)
        self._seed_email_change_verification('brand_new@example.com')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'pass-word-123!',
            'new_email': 'brand_new@example.com',
            'code': '123456',
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, 'brand_new@example.com')
        user.profile.refresh_from_db()
        self.assertIsNotNone(user.profile.email_last_changed_at)
        audit = SecurityAuditLog.objects.get(
            user=user,
            action=SecurityAuditLog.ACTION_EMAIL_CHANGED,
        )
        self.assertEqual(audit.actor, user)
        self.assertEqual(audit.metadata['old_email'], 'ue06@example.com')
        self.assertEqual(audit.metadata['new_email'], 'brand_new@example.com')

    def test_update_email_cooldown_blocks_second_change(self):
        user = make_user('ue08')
        user.profile.email_last_changed_at = timezone.now()
        user.profile.save(update_fields=['email_last_changed_at'])
        login(self.client, user)
        self._seed_email_change_verification('cooldown@example.com')
        response = post_json(self.client, reverse('update_email'), {
            'password': 'pass-word-123!',
            'new_email': 'cooldown@example.com',
            'code': '123456',
        })
        body = parse(response)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(body['status'], 'error')
        self.assertIn('cooldown_until', body)

    def test_invalid_json(self):
        user = make_user('ue07')
        login(self.client, user)
        response = self.client.post(
            reverse('update_email'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# =========================================================================
# security devices
# =========================================================================
class SecurityDeviceTests(_ProfileTestBase):
    def _create_device(self, user, *, session_key='', fingerprint='device-fp'):
        return LoginDevice.objects.create(
            user=user,
            device_fingerprint=fingerprint,
            ip_address='127.0.0.1',
            user_agent='Test browser',
            device_info='Test browser on Windows',
            session_key=session_key,
            is_active=True,
        )

    def test_security_devices_marks_current_session(self):
        user = make_user('sd01')
        login(self.client, user)
        current_session_key = self.client.session.session_key
        self._create_device(user, session_key=current_session_key, fingerprint='sd01-current')
        self._create_device(user, session_key='other-session', fingerprint='sd01-other')

        body = parse(self.client.get(reverse('security_devices_api')))

        self.assertEqual(body['status'], 'success')
        current_devices = [device for device in body['devices'] if device['is_current']]
        self.assertEqual(len(current_devices), 1)
        self.assertEqual(current_devices[0]['device_info'], 'Test browser on Windows')

    def test_revoke_security_device_deletes_session_and_writes_audit_log(self):
        user = make_user('sd02')
        login(self.client, user)
        other_session_key = 'sd02-other-session-key'
        Session.objects.create(
            session_key=other_session_key,
            session_data='',
            expire_date=timezone.now() + timedelta(days=1),
        )
        device = self._create_device(user, session_key=other_session_key, fingerprint='sd02-other')

        response = self.client.post(reverse('revoke_security_device_api', args=[device.id]))

        self.assertEqual(response.status_code, 200, response.content)
        device.refresh_from_db()
        self.assertFalse(device.is_active)
        self.assertEqual(device.revoked_by, user)
        self.assertIsNotNone(device.revoked_at)
        self.assertFalse(Session.objects.filter(session_key=other_session_key).exists())
        self.assertTrue(SecurityAuditLog.objects.filter(
            user=user,
            actor=user,
            action=SecurityAuditLog.ACTION_DEVICE_REVOKED,
            metadata__device_id=device.id,
        ).exists())

    def test_revoke_current_security_device_is_rejected(self):
        user = make_user('sd03')
        login(self.client, user)
        device = self._create_device(
            user,
            session_key=self.client.session.session_key,
            fingerprint='sd03-current',
        )

        response = self.client.post(reverse('revoke_security_device_api', args=[device.id]))

        self.assertEqual(response.status_code, 400)
        device.refresh_from_db()
        self.assertTrue(device.is_active)


# =========================================================================
# toggle_profile_like
# =========================================================================
class ToggleProfileLikeTests(_ProfileTestBase):
    def test_like_increases_count(self):
        user = make_user('lk01')
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_profile_like'), {})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertTrue(body['is_liked'])
        self.assertEqual(body['likes_count'], 1)
        self.assertTrue(ProfileLike.objects.filter(liker=user, profile=user.profile).exists())

    def test_unlike_decreases_count(self):
        user = make_user('lk02')
        ProfileLike.objects.create(liker=user, profile=user.profile)
        user.profile.likes_count = 1
        user.profile.save(update_fields=['likes_count'])
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_profile_like'), {})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertFalse(body['is_liked'])
        self.assertEqual(body['likes_count'], 0)
        self.assertFalse(ProfileLike.objects.filter(liker=user, profile=user.profile).exists())

    def test_requires_login(self):
        response = post_json(self.client, reverse('toggle_profile_like'), {})
        self.assertIn(response.status_code, (302, 401, 403))


# =========================================================================
# notification_preferences
# =========================================================================
class NotificationPreferencesTests(_ProfileTestBase):
    def test_get_default_preferences(self):
        user = make_user('np01')
        login(self.client, user)
        body = parse(self.client.get(reverse('notification_preferences')))
        self.assertEqual(body['status'], 'success')
        prefs = body['preferences']
        self.assertIn('notify_login', prefs)
        self.assertIn('email_messages', prefs)
        self.assertIn('notify_group_mentions_email', prefs)
        self.assertIn('email_mention_group_ids', prefs)
        self.assertIn('available_email_mention_groups', prefs)

    def test_update_profile_pref(self):
        user = make_user('np02')
        login(self.client, user)
        response = post_json(self.client, reverse('notification_preferences'), {
            'notify_login': False,
            'notify_note_activities': False,
        })
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.notify_login)
        self.assertFalse(user.profile.notify_note_activities)

    def test_update_message_pref(self):
        user = make_user('np03')
        login(self.client, user)
        response = post_json(self.client, reverse('notification_preferences'), {
            'email_messages': False,
            'browser_enabled': True,
        })
        self.assertEqual(response.status_code, 200)
        pref = MessagePreference.objects.get(user=user)
        self.assertFalse(pref.notify_new_message)
        self.assertTrue(pref.browser_new_message)

    def test_update_quiet_hours(self):
        user = make_user('np08')
        login(self.client, user)
        response = post_json(self.client, reverse('notification_preferences'), {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:30',
            'quiet_hours_end': '07:15',
        })

        self.assertEqual(response.status_code, 200, response.content)
        pref = MessagePreference.objects.get(user=user)
        self.assertTrue(pref.quiet_hours_enabled)
        self.assertEqual(pref.quiet_hours_start.strftime('%H:%M'), '22:30')
        self.assertEqual(pref.quiet_hours_end.strftime('%H:%M'), '07:15')
        body = parse(self.client.get(reverse('notification_preferences')))
        self.assertTrue(body['preferences']['quiet_hours_enabled'])
        self.assertEqual(body['preferences']['quiet_hours_start'], '22:30')
        self.assertEqual(body['preferences']['quiet_hours_end'], '07:15')

    def test_reject_invalid_quiet_hours(self):
        user = make_user('np09')
        login(self.client, user)
        response = post_json(self.client, reverse('notification_preferences'), {
            'quiet_hours_start': 'not-a-time',
        })
        self.assertEqual(response.status_code, 400)

    def test_update_group_mention_email_groups(self):
        user = make_user('np06')
        group = MessageGroup.objects.create(name='notify group', owner=user, created_by=user)
        MessageGroupMember.objects.create(group=group, user=user, role='owner')
        login(self.client, user)

        response = post_json(self.client, reverse('notification_preferences'), {
            'notify_group_mentions_email': True,
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 200, response.content)
        pref = MessagePreference.objects.get(user=user)
        self.assertTrue(pref.notify_group_mentions_email)
        self.assertEqual(list(pref.email_mention_groups.values_list('id', flat=True)), [group.id])

    def test_joined_group_is_available_for_group_mention_email(self):
        user = make_user('np06_member')
        owner = make_user('np06_owner')
        group = MessageGroup.objects.create(name='joined notify group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        MessageGroupMember.objects.create(group=group, user=user, role='member')
        login(self.client, user)

        body = parse(self.client.get(reverse('notification_preferences')))
        groups = body['preferences']['available_email_mention_groups']
        self.assertIn(group.id, [item['id'] for item in groups])

        response = post_json(self.client, reverse('notification_preferences'), {
            'notify_group_mentions_email': True,
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 200, response.content)
        pref = MessagePreference.objects.get(user=user)
        self.assertEqual(list(pref.email_mention_groups.values_list('id', flat=True)), [group.id])

    def test_reject_unavailable_group_mention_email_group(self):
        user = make_user('np07')
        owner = make_user('np07_owner')
        group = MessageGroup.objects.create(name='other group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        login(self.client, user)

        response = post_json(self.client, reverse('notification_preferences'), {
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 400)

    def test_empty_payload_returns_warning(self):
        user = make_user('np04')
        login(self.client, user)
        response = post_json(self.client, reverse('notification_preferences'), {})
        body = parse(response)
        self.assertEqual(body['status'], 'warning')

    def test_invalid_json(self):
        user = make_user('np05')
        login(self.client, user)
        response = self.client.post(
            reverse('notification_preferences'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# =========================================================================
# theme_settings
# =========================================================================
class ThemeSettingsTests(_ProfileTestBase):
    def test_get_default_theme(self):
        user = make_user('th01')
        login(self.client, user)
        body = parse(self.client.get(reverse('theme_settings')))
        self.assertEqual(body['status'], 'success')
        self.assertIn('settings', body)
        self.assertIn('mode', body['settings'])
        self.assertIn('primary_color', body['settings'])

    def test_update_theme(self):
        user = make_user('th02')
        login(self.client, user)
        response = post_json(self.client, reverse('theme_settings'), {
            'mode': 'dark',
            'primary_color': '#abcdef',
            'font_size': 16,
            'compact_mode': True,
            'animations': False,
        })
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['settings']['mode'], 'dark')
        self.assertEqual(body['settings']['primary_color'], '#abcdef')
        self.assertEqual(body['settings']['font_size'], 16)
        self.assertTrue(body['settings']['compact_mode'])
        self.assertFalse(body['settings']['animations'])

    def test_update_theme_via_legacy_primaryColor(self):
        user = make_user('th03')
        login(self.client, user)
        response = post_json(self.client, reverse('theme_settings'), {
            'primaryColor': '#112233',
        })
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.theme.get('primary_color'), '#112233')

    def test_update_layout(self):
        user = make_user('th04')
        login(self.client, user)
        response = post_json(self.client, reverse('theme_settings'), {'layout': 'sidebar'})
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.layout_mode, 'sidebar')

    def test_empty_payload_returns_warning(self):
        user = make_user('th05')
        login(self.client, user)
        response = post_json(self.client, reverse('theme_settings'), {})
        body = parse(response)
        self.assertEqual(body['status'], 'warning')

    def test_invalid_json(self):
        user = make_user('th06')
        login(self.client, user)
        response = self.client.post(
            reverse('theme_settings'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# =========================================================================
# user_public_profile_view
# =========================================================================
class UserPublicProfileViewTests(_ProfileTestBase):
    def test_view_renders_basic_info(self):
        target = make_user('pv01')
        Note.objects.create(author=target, title='公开1', content='', is_public=True)
        Note.objects.create(author=target, title='公开2', content='', is_public=True)
        Note.objects.create(author=target, title='私密', content='', is_public=False)
        response = self.client.get(reverse('user_public_profile', args=[target.id]))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['profile_user'].id, target.id)
        self.assertEqual(ctx['notes_count'], 2)  # 只统计公开笔记
        self.assertFalse(ctx['is_self'])
        self.assertFalse(ctx['is_authenticated'])

    def test_view_shows_is_self(self):
        user = make_user('pv02')
        login(self.client, user)
        response = self.client.get(reverse('user_public_profile', args=[user.id]))
        self.assertTrue(response.context['is_self'])

    def test_view_shows_following(self):
        a = make_user('pv03_a')
        b = make_user('pv03_b')
        UserFollow.objects.create(follower=a, following=b)
        login(self.client, a)
        response = self.client.get(reverse('user_public_profile', args=[b.id]))
        self.assertTrue(response.context['is_following'])
        self.assertFalse(response.context['is_self'])

    def test_view_shows_blocked_flags(self):
        a = make_user('pv04_a')
        b = make_user('pv04_b')
        UserBlocklist.objects.create(user=a, blocked_user=b)
        login(self.client, a)
        response = self.client.get(reverse('user_public_profile', args=[b.id]))
        self.assertTrue(response.context['is_blocked'])
        self.assertFalse(response.context['blocked_me'])

    def test_view_returns_404_for_nonexistent_user(self):
        response = self.client.get(reverse('user_public_profile', args=[9999999]))
        self.assertEqual(response.status_code, 404)

    def test_view_counts_followers(self):
        target = make_user('pv06')
        f1 = make_user('pv06_f1')
        f2 = make_user('pv06_f2')
        UserFollow.objects.create(follower=f1, following=target)
        UserFollow.objects.create(follower=f2, following=target)
        response = self.client.get(reverse('user_public_profile', args=[target.id]))
        self.assertEqual(response.context['followers_count'], 2)

    def test_view_records_non_self_visit(self):
        target = make_user('pv07_target')
        viewer = make_user('pv07_viewer')
        login(self.client, viewer)
        response = self.client.get(reverse('user_public_profile', args=[target.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProfileVisit.objects.filter(profile=target.profile, viewer=viewer).count(), 1)
        self.assertEqual(response.context['views_count'], 1)

    def test_view_does_not_record_self_visit(self):
        user = make_user('pv08')
        login(self.client, user)
        response = self.client.get(reverse('user_public_profile', args=[user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProfileVisit.objects.filter(profile=user.profile).count(), 0)


# =========================================================================
# settings_view
# =========================================================================
class SettingsViewTests(_ProfileTestBase):
    def test_view_requires_login(self):
        response = self.client.get(reverse('settings'))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_view_renders_for_logged_in_user(self):
        user = make_user('sv01')
        login(self.client, user)
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['nickname'], user.username)
        self.assertEqual(ctx['email'], user.email)

    def test_view_shows_profile_visit_count(self):
        user = make_user('sv02')
        viewer = make_user('sv02_viewer')
        ProfileVisit.objects.create(profile=user.profile, viewer=viewer, session_key='s')
        login(self.client, user)
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.context['views_count'], 1)


class NotificationCenterApiTests(_ProfileTestBase):
    def test_list_notifications_and_unread_count(self):
        user = make_user('nc01')
        UserNotification.objects.create(user=user, kind='new_comment', title='A', body='body')
        UserNotification.objects.create(user=user, kind='new_message', title='B', is_read=True)
        login(self.client, user)

        body = parse(self.client.get(reverse('notifications_list_api')))

        self.assertEqual(body['status'], 'success')
        self.assertEqual(len(body['notifications']), 2)
        self.assertEqual(body['unread_count'], 1)

        count_body = parse(self.client.get(reverse('notifications_unread_count_api')))
        self.assertEqual(count_body['unread_count'], 1)

    def test_mark_selected_notification_read(self):
        user = make_user('nc02')
        first = UserNotification.objects.create(user=user, kind='new_comment', title='A')
        second = UserNotification.objects.create(user=user, kind='new_message', title='B')
        login(self.client, user)

        response = post_json(self.client, reverse('notifications_mark_read_api'), {
            'notification_ids': [first.id],
        })

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertFalse(second.is_read)
        self.assertEqual(parse(response)['unread_count'], 1)

    def test_mark_all_notifications_read(self):
        user = make_user('nc03')
        UserNotification.objects.create(user=user, kind='new_comment', title='A')
        UserNotification.objects.create(user=user, kind='new_message', title='B')
        login(self.client, user)

        response = post_json(self.client, reverse('notifications_mark_read_api'), {'all': True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserNotification.objects.filter(user=user, is_read=False).count(), 0)
