"""message 模块测试

覆盖:
- send_message_api / forward_message_api
- get_messages_api / get_message_conversations_api
- delete_message_api / bulk_delete_messages_api / clear_conversation_api
- mark_conversation_read_api / mark_conversation_unread_api
- toggle_pin_api / toggle_mute_api / toggle_archive_api
- set_disappearing_api / get_conversation_settings_api
- search_messages_api / export_conversation_api
- report_user_api
- block_user_api / unblock_user_api / get_blocked_users_api
- get_message_preference_api / update_message_preference_api
- get_unread_messages_count_api
- get_user_public_profile_api / search_users_api
- update_discoverability_api / touch_messages_page_api
- 新对话配额(Turnstile) 限流分支

注: MessagePreference 有 post_save 信号在 User 创建时自动建表 (默认 allow_messages=False),
因此本文件统一通过 _enable_messaging() 显式打开接收开关。
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from knowledge_project.models import (
    ConversationSettings,
    GroupMessage,
    Message,
    MessageAttachment,
    MessageGroup,
    MessageGroupAuditLog,
    MessageGroupBan,
    MessageGroupInviteLink,
    MessageGroupMember,
    MessageGroupPolicy,
    NoteComment,
    MessagePreference,
    MessageReport,
    ModerationAppeal,
    ModerationLog,
    ModerationTemplate,
    CommentReport,
    Note,
    NoteReport,
    NewConversationQuotaLog,
    UserBlocklist,
    UserFollow,
    UserNotification,
    UserSanction,
)

from ._helpers import login, make_user, parse, post_json


def _enable_messaging(user, mode: str = 'all') -> MessagePreference:
    """打开 user 的接收开关。signal 已创建过 pref,这里走 update 路径。"""
    pref, _ = MessagePreference.objects.get_or_create(user=user)
    pref.allow_messages = True
    pref.message_mode = mode
    pref.save()
    return pref


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _MessageTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# send_message_api
# =========================================================================
class SendMessageApiTests(_MessageTestBase):
    def test_send_message_success(self):
        sender = make_user('snd01_s')
        recipient = make_user('snd01_r')
        _enable_messaging(recipient)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hello world',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Message.objects.filter(sender=sender, recipient=recipient, content='hello world').exists()
        )

    def test_cannot_send_to_self(self):
        user = make_user('snd02')
        login(self.client, user)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': user.id,
            'content': 'self talk',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('自己', parse(response)['error'])

    def test_recipient_blocked_sender(self):
        sender = make_user('snd03_s')
        recipient = make_user('snd03_r')
        _enable_messaging(recipient)
        UserBlocklist.objects.create(user=recipient, blocked_user=sender)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.filter(sender=sender, recipient=recipient).exists())

    def test_sender_blocked_recipient(self):
        sender = make_user('snd04_s')
        recipient = make_user('snd04_r')
        _enable_messaging(recipient)
        UserBlocklist.objects.create(user=sender, blocked_user=recipient)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('屏蔽', parse(response)['error'])

    def test_recipient_disabled_messages(self):
        sender = make_user('snd05_s')
        recipient = make_user('snd05_r')
        _enable_messaging(recipient, mode='disabled')
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 403)

    def test_recipient_followers_only_blocks_non_follower(self):
        sender = make_user('snd06_s')
        recipient = make_user('snd06_r')
        _enable_messaging(recipient, mode='followers_only')
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn('关注', parse(response)['error'])

    def test_recipient_followers_only_allows_follower(self):
        sender = make_user('snd07_s')
        recipient = make_user('snd07_r')
        _enable_messaging(recipient, mode='followers_only')
        UserFollow.objects.create(follower=sender, following=recipient)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 201)

    def test_recipient_following_only_blocks_non_followed(self):
        sender = make_user('snd07b_s')
        recipient = make_user('snd07b_r')
        _enable_messaging(recipient, mode='following_only')
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 403)

    def test_recipient_following_only_allows_followed(self):
        sender = make_user('snd07c_s')
        recipient = make_user('snd07c_r')
        _enable_messaging(recipient, mode='following_only')
        UserFollow.objects.create(follower=recipient, following=sender)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 201)

    def test_missing_recipient_id_returns_400(self):
        sender = make_user('snd08')
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {'content': 'hi'})
        self.assertEqual(response.status_code, 400)

    def test_empty_content_returns_400(self):
        sender = make_user('snd09_s')
        recipient = make_user('snd09_r')
        _enable_messaging(recipient)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': '',
        })
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        sender = make_user('snd10')
        login(self.client, sender)
        response = self.client.post(
            reverse('send_message_api'), data='not-json', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_content_too_long_returns_400(self):
        sender = make_user('snd11_s')
        recipient = make_user('snd11_r')
        _enable_messaging(recipient)
        login(self.client, sender)
        # 5001 字符 > MESSAGE_CONTENT_MAX_LENGTH 5000
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'a' * 5001,
        })
        self.assertEqual(response.status_code, 400)

    def test_anonymous_user_redirected(self):
        recipient = make_user('snd12_r')
        # 未登录: login_required 应当拦截(302 重定向到 login)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'hi',
        })
        self.assertIn(response.status_code, (302, 401, 403))


# =========================================================================
# message groups
# =========================================================================
class MessageGroupTests(_MessageTestBase):
    def _make_public_notes(self, user, count):
        for i in range(count):
            Note.objects.create(
                author=user,
                title=f'public note {i}',
                content='<p>public content</p>',
                is_public=True,
            )

    def _create_group_directly(self, owner, members):
        group = MessageGroup.objects.create(name='direct group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        for member in members:
            MessageGroupMember.objects.create(group=group, user=member, role='member')
        return group

    def test_group_policy_defaults_are_configurable_values(self):
        user = make_user('grp_policy_user')
        login(self.client, user)
        body = parse(self.client.get(reverse('get_group_policy_api')))
        policy = body['policy']
        self.assertTrue(policy['enabled'])
        self.assertEqual(policy['min_public_notes'], 10)
        self.assertEqual(policy['min_followers'], 50)
        self.assertFalse(policy['eligible'])

    def test_non_admin_cannot_update_group_policy(self):
        user = make_user('grp_policy_non_admin')
        login(self.client, user)
        response = post_json(self.client, reverse('get_group_policy_api'), {
            'enabled': False,
            'min_public_notes': 1,
            'min_followers': 1,
        })
        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_group_policy(self):
        admin = make_user('grp_policy_admin', is_staff=True)
        login(self.client, admin)
        response = post_json(self.client, reverse('get_group_policy_api'), {
            'enabled': False,
            'min_public_notes': 3,
            'min_followers': 7,
        })
        self.assertEqual(response.status_code, 200, response.content)
        policy = parse(response)['policy']
        self.assertFalse(policy['enabled'])
        self.assertEqual(policy['min_public_notes'], 3)
        self.assertEqual(policy['min_followers'], 7)
        self.assertTrue(policy['can_manage'])

    def test_ineligible_user_cannot_create_group(self):
        owner = make_user('grp_ineligible_owner')
        member = make_user('grp_ineligible_member')
        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'blocked group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MessageGroup.objects.exists())

    def test_user_with_required_public_notes_can_create_group(self):
        owner = make_user('grp_notes_owner')
        member = make_user('grp_notes_member')
        self._make_public_notes(owner, 10)
        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'notes group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 201, response.content)
        group = MessageGroup.objects.get(name='notes group')
        self.assertEqual(group.owner, owner)
        self.assertEqual(group.memberships.filter(left_at__isnull=True).count(), 2)

    def test_admin_adjusted_follower_threshold_is_used(self):
        owner = make_user('grp_follow_owner')
        member = make_user('grp_follow_member')
        MessageGroupPolicy.objects.create(min_public_notes=99, min_followers=2)
        for i in range(2):
            follower = make_user(f'grp_follow_follower_{i}')
            UserFollow.objects.create(follower=follower, following=owner)

        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'followers group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 201, response.content)

    def test_disabled_group_policy_blocks_creation_even_when_threshold_met(self):
        owner = make_user('grp_disabled_owner')
        member = make_user('grp_disabled_member')
        self._make_public_notes(owner, 10)
        MessageGroupPolicy.objects.create(enabled=False)
        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'disabled group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 403)

    def test_group_message_send_list_recall_and_report(self):
        owner = make_user('grp_msg_owner')
        member = make_user('grp_msg_member')
        group = self._create_group_directly(owner, [member])

        login(self.client, owner)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'hello group',
        })
        self.assertEqual(response.status_code, 201, response.content)
        message = GroupMessage.objects.get(group=group, sender=owner)

        self.client.logout()
        login(self.client, member)
        body = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))
        self.assertEqual(body['conversation_type'], 'group')
        self.assertFalse(body['settings']['disappearing_enabled'])
        self.assertEqual(body['messages'][0]['content'], 'hello group')

        report_response = post_json(self.client, reverse('report_group_message_api', args=[group.id, message.id]), {
            'reason': 'abuse',
            'detail': 'bad group message',
        })
        self.assertEqual(report_response.status_code, 200, report_response.content)
        message.refresh_from_db()
        self.assertTrue(message.was_reported)
        self.assertTrue(MessageReport.objects.filter(group_message=message, reported_user=owner).exists())

        self.client.logout()
        login(self.client, owner)
        recall_response = post_json(self.client, reverse('delete_group_message_api', args=[group.id, message.id]), {
            'scope': 'both',
        })
        self.assertEqual(recall_response.status_code, 200, recall_response.content)
        message.refresh_from_db()
        self.assertTrue(message.is_recalled)

    def test_group_owner_can_manage_members_and_group_name(self):
        owner = make_user('grp_manage_owner')
        member = make_user('grp_manage_member')
        newcomer = make_user('grp_manage_newcomer')
        group = self._create_group_directly(owner, [member])
        login(self.client, owner)

        rename_response = post_json(self.client, reverse('message_group_detail_api', args=[group.id]), {
            'name': 'renamed group',
        })
        self.assertEqual(rename_response.status_code, 200, rename_response.content)
        group.refresh_from_db()
        self.assertEqual(group.name, 'renamed group')

        add_response = post_json(self.client, reverse('add_group_members_api', args=[group.id]), {
            'member_ids': [newcomer.id],
        })
        self.assertEqual(add_response.status_code, 200, add_response.content)
        self.assertTrue(MessageGroupMember.objects.filter(group=group, user=newcomer, left_at__isnull=True).exists())

        remove_response = post_json(self.client, reverse('remove_group_member_api', args=[group.id, newcomer.id]), {})
        self.assertEqual(remove_response.status_code, 200, remove_response.content)
        self.assertFalse(MessageGroupMember.objects.filter(group=group, user=newcomer, left_at__isnull=True).exists())

    def test_group_member_cannot_manage_members(self):
        owner = make_user('grp_manage2_owner')
        member = make_user('grp_manage2_member')
        newcomer = make_user('grp_manage2_newcomer')
        group = self._create_group_directly(owner, [member])
        login(self.client, member)

        response = post_json(self.client, reverse('add_group_members_api', args=[group.id]), {
            'member_ids': [newcomer.id],
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(MessageGroupMember.objects.filter(group=group, user=newcomer).exists())

    def test_group_owner_can_promote_admin_and_admin_cannot_promote(self):
        owner = make_user('grp_role_owner')
        member = make_user('grp_role_member')
        admin_target = make_user('grp_role_admin_target')
        group = self._create_group_directly(owner, [member, admin_target])
        login(self.client, owner)

        response = post_json(self.client, reverse('set_group_member_role_api', args=[group.id, member.id]), {
            'role': 'admin',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(MessageGroupMember.objects.get(group=group, user=member).role, 'admin')

        self.client.logout()
        login(self.client, member)
        response = post_json(self.client, reverse('set_group_member_role_api', args=[group.id, admin_target.id]), {
            'role': 'admin',
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(MessageGroupMember.objects.get(group=group, user=admin_target).role, 'member')

    def test_group_manager_can_mute_member_and_unmute(self):
        owner = make_user('grp_mute_owner')
        member = make_user('grp_mute_member')
        group = self._create_group_directly(owner, [member])
        login(self.client, owner)

        response = post_json(self.client, reverse('mute_group_member_api', args=[group.id, member.id]), {
            'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 200, response.content)
        membership = MessageGroupMember.objects.get(group=group, user=member)
        self.assertIsNotNone(membership.muted_until)

        self.client.logout()
        login(self.client, member)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'muted hello',
        })
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(GroupMessage.objects.filter(group=group, sender=member, content='muted hello').exists())

        self.client.logout()
        login(self.client, owner)
        response = post_json(self.client, reverse('mute_group_member_api', args=[group.id, member.id]), {
            'action': 'unmute',
        })
        self.assertEqual(response.status_code, 200, response.content)
        membership.refresh_from_db()
        self.assertIsNone(membership.muted_until)

        self.client.logout()
        login(self.client, member)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'unmuted hello',
        })
        self.assertEqual(response.status_code, 201, response.content)

    def test_group_invite_link_join_and_revoke(self):
        owner = make_user('grp_invite_owner')
        member = make_user('grp_invite_member')
        outsider = make_user('grp_invite_outsider')
        late_user = make_user('grp_invite_late')
        group = self._create_group_directly(owner, [member])
        login(self.client, owner)

        response = post_json(self.client, reverse('group_invite_links_api', args=[group.id]), {})
        self.assertEqual(response.status_code, 201, response.content)
        invite = MessageGroupInviteLink.objects.get(group=group)
        self.assertIn('group_invite=', parse(response)['invite']['url'])

        self.client.logout()
        login(self.client, outsider)
        response = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(MessageGroupMember.objects.filter(group=group, user=outsider, left_at__isnull=True).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.uses_count, 1)

        self.client.logout()
        login(self.client, owner)
        response = post_json(self.client, reverse('revoke_group_invite_link_api', args=[group.id, invite.id]), {})
        self.assertEqual(response.status_code, 200, response.content)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.revoked_at)

        self.client.logout()
        login(self.client, late_user)
        response = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(MessageGroupMember.objects.filter(group=group, user=late_user, left_at__isnull=True).exists())

    def test_group_message_sender_can_edit_sent_message(self):
        owner = make_user('grp_edit_owner')
        member = make_user('grp_edit_member')
        group = self._create_group_directly(owner, [member])
        message = GroupMessage.objects.create(group=group, sender=owner, content='old content')
        login(self.client, owner)

        response = post_json(self.client, reverse('edit_group_message_api', args=[group.id, message.id]), {
            'content': 'new content',
        })
        self.assertEqual(response.status_code, 200, response.content)
        message.refresh_from_db()
        self.assertEqual(message.content, 'new content')
        self.assertTrue(message.is_edited)
        self.assertIsNotNone(message.edited_at)
        body = parse(response)
        self.assertEqual(body['message']['content'], 'new content')
        self.assertTrue(body['message']['is_edited'])

    def test_group_member_cannot_edit_other_member_message(self):
        owner = make_user('grp_edit2_owner')
        member = make_user('grp_edit2_member')
        group = self._create_group_directly(owner, [member])
        message = GroupMessage.objects.create(group=group, sender=owner, content='owner content')
        login(self.client, member)

        response = post_json(self.client, reverse('edit_group_message_api', args=[group.id, message.id]), {
            'content': 'changed',
        })
        self.assertEqual(response.status_code, 403, response.content)
        message.refresh_from_db()
        self.assertEqual(message.content, 'owner content')

    def test_group_personal_settings_leave_and_dissolve(self):
        owner = make_user('grp_settings_owner')
        member = make_user('grp_settings_member')
        group = self._create_group_directly(owner, [member])
        login(self.client, member)

        response = post_json(self.client, reverse('toggle_group_setting_api', args=[group.id, 'pin']), {'value': True})
        self.assertEqual(response.status_code, 200, response.content)
        membership = MessageGroupMember.objects.get(group=group, user=member)
        self.assertTrue(membership.is_pinned)

        response = post_json(self.client, reverse('toggle_group_setting_api', args=[group.id, 'clear']), {})
        self.assertEqual(response.status_code, 200, response.content)
        membership.refresh_from_db()
        self.assertIsNotNone(membership.cleared_before)

        response = post_json(self.client, reverse('leave_message_group_api', args=[group.id]), {})
        self.assertEqual(response.status_code, 200, response.content)
        membership.refresh_from_db()
        self.assertIsNotNone(membership.left_at)

        self.client.logout()
        login(self.client, owner)
        response = post_json(self.client, reverse('dissolve_message_group_api', args=[group.id]), {})
        self.assertEqual(response.status_code, 200, response.content)
        group.refresh_from_db()
        self.assertFalse(group.is_active)

    def test_group_profile_transfer_mute_mode_and_audit_logs(self):
        owner = make_user('grp_ext_owner')
        member = make_user('grp_ext_member')
        admin_user = make_user('grp_ext_admin')
        group = self._create_group_directly(owner, [member, admin_user])
        MessageGroupMember.objects.filter(group=group, user=admin_user).update(role='admin')
        login(self.client, owner)

        profile_response = post_json(self.client, reverse('update_group_profile_api', args=[group.id]), {
            'name': 'advanced group',
            'description': 'group description',
            'announcement': 'group announcement',
        })
        self.assertEqual(profile_response.status_code, 200, profile_response.content)
        group.refresh_from_db()
        self.assertEqual(group.name, 'advanced group')
        self.assertEqual(group.description, 'group description')
        self.assertEqual(group.announcement, 'group announcement')

        mute_response = post_json(self.client, reverse('set_group_mute_mode_api', args=[group.id]), {
            'mute_mode': 'admins_only',
        })
        self.assertEqual(mute_response.status_code, 200, mute_response.content)
        group.refresh_from_db()
        self.assertEqual(group.mute_mode, 'admins_only')

        self.client.logout()
        login(self.client, member)
        blocked_send = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'member blocked by group mute',
        })
        self.assertEqual(blocked_send.status_code, 403, blocked_send.content)

        self.client.logout()
        login(self.client, admin_user)
        allowed_send = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'admin can speak',
        })
        self.assertEqual(allowed_send.status_code, 201, allowed_send.content)

        self.client.logout()
        login(self.client, owner)
        transfer_response = post_json(self.client, reverse('transfer_group_ownership_api', args=[group.id]), {
            'user_id': member.id,
        })
        self.assertEqual(transfer_response.status_code, 200, transfer_response.content)
        group.refresh_from_db()
        self.assertEqual(group.owner, member)
        self.assertEqual(MessageGroupMember.objects.get(group=group, user=member).role, 'owner')
        self.assertEqual(MessageGroupMember.objects.get(group=group, user=owner).role, 'admin')
        self.assertTrue(MessageGroupAuditLog.objects.filter(group=group, action='ownership_transfer').exists())

    def test_group_ban_blocks_invite_join_and_unban_allows_rejoin(self):
        owner = make_user('grp_ban_owner')
        member = make_user('grp_ban_member')
        outsider = make_user('grp_ban_outsider')
        group = self._create_group_directly(owner, [member])
        invite = MessageGroupInviteLink.objects.create(group=group, created_by=owner)
        login(self.client, owner)

        ban_response = post_json(self.client, reverse('group_bans_api', args=[group.id]), {
            'user_id': outsider.id,
            'reason': 'spam',
        })
        self.assertEqual(ban_response.status_code, 201, ban_response.content)
        ban = MessageGroupBan.objects.get(group=group, user=outsider)
        self.assertTrue(ban.is_active())

        self.client.logout()
        login(self.client, outsider)
        preview = parse(self.client.get(reverse('preview_group_invite_api', args=[invite.token])))
        self.assertFalse(preview['viewer']['can_join'])
        self.assertTrue(preview['viewer']['is_banned'])
        join_response = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(join_response.status_code, 403, join_response.content)

        self.client.logout()
        login(self.client, owner)
        unban_response = post_json(self.client, reverse('revoke_group_ban_api', args=[group.id, ban.id]), {})
        self.assertEqual(unban_response.status_code, 200, unban_response.content)
        ban.refresh_from_db()
        self.assertIsNotNone(ban.revoked_at)

        self.client.logout()
        login(self.client, outsider)
        join_response = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(join_response.status_code, 200, join_response.content)
        self.assertTrue(MessageGroupMember.objects.filter(group=group, user=outsider, left_at__isnull=True).exists())

    def test_group_audit_logs_are_manager_only(self):
        owner = make_user('grp_audit_owner')
        member = make_user('grp_audit_member')
        group = self._create_group_directly(owner, [member])
        MessageGroupAuditLog.objects.create(group=group, actor=owner, action='group_update_profile')

        login(self.client, member)
        forbidden = self.client.get(reverse('group_audit_logs_api', args=[group.id]))
        self.assertEqual(forbidden.status_code, 403, forbidden.content)

        self.client.logout()
        login(self.client, owner)
        response = self.client.get(reverse('group_audit_logs_api', args=[group.id]))
        self.assertEqual(response.status_code, 200, response.content)
        body = parse(response)
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['results'][0]['action'], 'group_update_profile')


# =========================================================================
# forward_message_api
# =========================================================================
class ForwardMessageApiTests(_MessageTestBase):
    def test_forward_message_to_new_user(self):
        sender = make_user('fwd01_s')
        original_recipient = make_user('fwd01_or')
        new_recipient = make_user('fwd01_nr')
        _enable_messaging(original_recipient)
        _enable_messaging(new_recipient)
        src = Message.objects.create(sender=sender, recipient=original_recipient, content='原内容')
        login(self.client, sender)
        response = post_json(self.client, reverse('forward_message_api'), {
            'message_id': src.id,
            'recipient_id': new_recipient.id,
        })
        self.assertEqual(response.status_code, 201)
        # 应该有 2 条 Message: 原始 + 转发
        forwarded = Message.objects.filter(sender=sender, recipient=new_recipient)
        self.assertTrue(forwarded.exists())
        self.assertEqual(forwarded.first().content, '原内容')

    def test_forward_missing_params(self):
        sender = make_user('fwd02')
        login(self.client, sender)
        response = post_json(self.client, reverse('forward_message_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_forward_unrelated_message_forbidden(self):
        outsider = make_user('fwd03_o')
        a = make_user('fwd03_a')
        b = make_user('fwd03_b')
        _enable_messaging(outsider)
        src = Message.objects.create(sender=a, recipient=b, content='私密')
        login(self.client, outsider)
        response = post_json(self.client, reverse('forward_message_api'), {
            'message_id': src.id,
            'recipient_id': outsider.id,
        })
        # outsider 既不是 sender 也不是 recipient,不能转发
        self.assertEqual(response.status_code, 403)


# =========================================================================
# get_messages_api
# =========================================================================
class GetMessagesApiTests(_MessageTestBase):
    def test_get_messages_returns_both_directions(self):
        alice = make_user('gm01_a')
        bob = make_user('gm01_b')
        Message.objects.create(sender=alice, recipient=bob, content='A→B')
        Message.objects.create(sender=bob, recipient=alice, content='B→A')
        login(self.client, alice)
        response = self.client.get(reverse('get_messages_api') + f'?user_id={bob.id}')
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        contents = {m['content'] for m in body['messages']}
        self.assertEqual(contents, {'A→B', 'B→A'})

    def test_get_messages_marks_received_as_read(self):
        alice = make_user('gm02_a')
        bob = make_user('gm02_b')
        m1 = Message.objects.create(sender=bob, recipient=alice, content='x', is_read=False)
        m2 = Message.objects.create(sender=bob, recipient=alice, content='y', is_read=False)
        login(self.client, alice)
        self.client.get(reverse('get_messages_api') + f'?user_id={bob.id}')
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertTrue(m1.is_read)
        self.assertTrue(m2.is_read)

    def test_get_messages_excludes_recalled(self):
        alice = make_user('gm03_a')
        bob = make_user('gm03_b')
        Message.objects.create(sender=alice, recipient=bob, content='正常')
        Message.objects.create(
            sender=alice, recipient=bob, content='已撤回', is_recalled=True,
        )
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_messages_api') + f'?user_id={bob.id}'))
        contents = {m['content'] for m in body['messages']}
        self.assertEqual(contents, {'正常'})

    def test_get_messages_supports_query_search(self):
        alice = make_user('gm04_a')
        bob = make_user('gm04_b')
        Message.objects.create(sender=alice, recipient=bob, content='今天去打篮球', searchable_text='今天去打篮球')
        Message.objects.create(sender=bob, recipient=alice, content='不用了 我去看电影', searchable_text='不用了 我去看电影')
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_messages_api') + f'?user_id={bob.id}&q=篮球'))
        contents = {m['content'] for m in body['messages']}
        self.assertEqual(contents, {'今天去打篮球'})

    def test_missing_user_id_returns_400(self):
        user = make_user('gm05')
        login(self.client, user)
        response = self.client.get(reverse('get_messages_api'))
        self.assertEqual(response.status_code, 400)


# =========================================================================
# get_message_conversations_api
# =========================================================================
class ConversationListTests(_MessageTestBase):
    def test_empty_user_returns_empty_list(self):
        user = make_user('cv01')
        login(self.client, user)
        body = parse(self.client.get(reverse('get_message_conversations_api')))
        self.assertEqual(body.get('conversations', []), [])

    def test_lists_each_peer_once(self):
        alice = make_user('cv02_a')
        bob = make_user('cv02_b')
        Message.objects.create(sender=alice, recipient=bob, content='m1')
        Message.objects.create(sender=bob, recipient=alice, content='m2')
        Message.objects.create(sender=alice, recipient=bob, content='m3')
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_message_conversations_api')))
        peer_ids = [c['user_id'] for c in body['conversations']]
        self.assertEqual(peer_ids, [bob.id])

    def test_blocked_scope_returns_block_list(self):
        user = make_user('cv03')
        blocked = make_user('cv03_blocked')
        UserBlocklist.objects.create(user=user, blocked_user=blocked)
        login(self.client, user)
        body = parse(self.client.get(reverse('get_message_conversations_api') + '?scope=blocked'))
        items = body.get('conversations') or body.get('blocked_users') or body
        self.assertTrue(any(u.get('user_id') == blocked.id or u.get('username') == blocked.username
                            for u in items))

    def test_unread_scope_filters_read_conversations(self):
        alice = make_user('cv04_a')
        bob = make_user('cv04_b')
        carol = make_user('cv04_c')
        # bob → alice 未读
        Message.objects.create(sender=bob, recipient=alice, content='unread', is_read=False)
        # alice → carol 已读(没有未读)
        Message.objects.create(sender=alice, recipient=carol, content='sent')
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_message_conversations_api') + '?scope=unread'))
        peer_ids = [c['user_id'] for c in body['conversations']]
        self.assertEqual(peer_ids, [bob.id])


# =========================================================================
# delete_message_api / bulk_delete_messages_api / clear_conversation_api
# =========================================================================
class DeleteMessageApiTests(_MessageTestBase):
    def test_self_delete_hides_for_sender_only(self):
        alice = make_user('dl01_a')
        bob = make_user('dl01_b')
        msg = Message.objects.create(sender=alice, recipient=bob, content='hello')
        login(self.client, alice)
        response = post_json(self.client, reverse('delete_message_api', args=[msg.id]), {'scope': 'self'})
        self.assertEqual(response.status_code, 200)
        msg.refresh_from_db()
        self.assertTrue(msg.deleted_for_sender)
        self.assertFalse(msg.deleted_for_recipient)
        self.assertFalse(msg.is_recalled)

    def test_recall_within_window(self):
        alice = make_user('dl02_a')
        bob = make_user('dl02_b')
        msg = Message.objects.create(sender=alice, recipient=bob, content='oops')
        login(self.client, alice)
        response = post_json(self.client, reverse('delete_message_api', args=[msg.id]), {'scope': 'both'})
        self.assertEqual(response.status_code, 200)
        msg.refresh_from_db()
        self.assertTrue(msg.is_recalled)

    def test_recall_after_window_rejected(self):
        alice = make_user('dl03_a')
        bob = make_user('dl03_b')
        msg = Message.objects.create(sender=alice, recipient=bob, content='old')
        # 模拟超过 120s 窗口
        Message.objects.filter(pk=msg.pk).update(
            created_at=timezone.now() - timedelta(seconds=300)
        )
        login(self.client, alice)
        response = post_json(self.client, reverse('delete_message_api', args=[msg.id]), {'scope': 'both'})
        self.assertEqual(response.status_code, 403)
        msg.refresh_from_db()
        self.assertFalse(msg.is_recalled)

    def test_only_sender_can_recall(self):
        alice = make_user('dl04_a')
        bob = make_user('dl04_b')
        msg = Message.objects.create(sender=alice, recipient=bob, content='alice 发的')
        login(self.client, bob)
        response = post_json(self.client, reverse('delete_message_api', args=[msg.id]), {'scope': 'both'})
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_delete(self):
        alice = make_user('dl05_a')
        bob = make_user('dl05_b')
        outsider = make_user('dl05_o')
        msg = Message.objects.create(sender=alice, recipient=bob, content='私密')
        login(self.client, outsider)
        response = post_json(self.client, reverse('delete_message_api', args=[msg.id]), {'scope': 'self'})
        self.assertEqual(response.status_code, 403)


class BulkDeleteMessagesApiTests(_MessageTestBase):
    def test_bulk_delete_marks_messages_hidden(self):
        alice = make_user('bd01_a')
        bob = make_user('bd01_b')
        m1 = Message.objects.create(sender=alice, recipient=bob, content='m1')
        m2 = Message.objects.create(sender=bob, recipient=alice, content='m2')
        login(self.client, alice)
        response = post_json(self.client, reverse('bulk_delete_messages_api'), {
            'message_ids': [m1.id, m2.id],
        })
        self.assertEqual(response.status_code, 200)
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertTrue(m1.deleted_for_sender)  # alice 是发送者
        self.assertTrue(m2.deleted_for_recipient)  # alice 是接收者

    def test_bulk_delete_empty_list_rejected(self):
        user = make_user('bd02')
        login(self.client, user)
        response = post_json(self.client, reverse('bulk_delete_messages_api'), {'message_ids': []})
        self.assertEqual(response.status_code, 400)

    def test_bulk_delete_rejects_unrelated_messages(self):
        alice = make_user('bd03_a')
        bob = make_user('bd03_b')
        carol = make_user('bd03_c')
        m1 = Message.objects.create(sender=alice, recipient=bob, content='ab')
        m_other = Message.objects.create(sender=bob, recipient=carol, content='bc')
        login(self.client, alice)
        response = post_json(self.client, reverse('bulk_delete_messages_api'), {
            'message_ids': [m1.id, m_other.id],
        })
        self.assertEqual(response.status_code, 403)


class ClearConversationApiTests(_MessageTestBase):
    def test_clear_sets_cleared_before(self):
        alice = make_user('cl01_a')
        bob = make_user('cl01_b')
        Message.objects.create(sender=alice, recipient=bob, content='m1')
        login(self.client, alice)
        response = post_json(self.client, reverse('clear_conversation_api'), {'user_id': bob.id})
        self.assertEqual(response.status_code, 200)
        cs = ConversationSettings.objects.get(user=alice, peer=bob)
        self.assertIsNotNone(cs.cleared_before)
        # 消息记录还在数据库
        self.assertTrue(Message.objects.filter(content='m1').exists())

    def test_clear_missing_user_id(self):
        user = make_user('cl02')
        login(self.client, user)
        response = post_json(self.client, reverse('clear_conversation_api'), {})
        self.assertEqual(response.status_code, 400)


# =========================================================================
# mark_conversation_read_api / mark_conversation_unread_api
# =========================================================================
class ConversationReadStateTests(_MessageTestBase):
    def test_mark_conversation_read(self):
        alice = make_user('rs01_a')
        bob = make_user('rs01_b')
        Message.objects.create(sender=bob, recipient=alice, content='x', is_read=False)
        Message.objects.create(sender=bob, recipient=alice, content='y', is_read=False)
        login(self.client, alice)
        response = post_json(self.client, reverse('mark_conversation_read_api'), {'user_id': bob.id})
        self.assertEqual(response.status_code, 200)
        unread = Message.objects.filter(sender=bob, recipient=alice, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_mark_conversation_unread(self):
        alice = make_user('rs02_a')
        bob = make_user('rs02_b')
        login(self.client, alice)
        response = post_json(self.client, reverse('mark_conversation_unread_api'), {'user_id': bob.id})
        self.assertEqual(response.status_code, 200)
        cs = ConversationSettings.objects.get(user=alice, peer=bob)
        self.assertTrue(cs.force_unread)

    def test_mark_unread_invalid_body(self):
        user = make_user('rs03')
        login(self.client, user)
        response = self.client.post(
            reverse('mark_conversation_unread_api'),
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


# =========================================================================
# toggle_pin / toggle_mute / toggle_archive
# =========================================================================
class ConversationToggleTests(_MessageTestBase):
    def test_toggle_pin(self):
        a = make_user('tp01_a')
        b = make_user('tp01_b')
        login(self.client, a)
        response = post_json(self.client, reverse('toggle_pin_api'), {'user_id': b.id, 'value': True})
        self.assertEqual(response.status_code, 200)
        cs = ConversationSettings.objects.get(user=a, peer=b)
        self.assertTrue(cs.is_pinned)
        self.assertIsNotNone(cs.pinned_at)
        # 取消
        post_json(self.client, reverse('toggle_pin_api'), {'user_id': b.id, 'value': False})
        cs.refresh_from_db()
        self.assertFalse(cs.is_pinned)
        self.assertIsNone(cs.pinned_at)

    def test_toggle_mute(self):
        a = make_user('tp02_a')
        b = make_user('tp02_b')
        login(self.client, a)
        post_json(self.client, reverse('toggle_mute_api'), {'user_id': b.id, 'value': True})
        cs = ConversationSettings.objects.get(user=a, peer=b)
        self.assertTrue(cs.is_muted)

    def test_toggle_archive(self):
        a = make_user('tp03_a')
        b = make_user('tp03_b')
        login(self.client, a)
        post_json(self.client, reverse('toggle_archive_api'), {'user_id': b.id, 'value': True})
        cs = ConversationSettings.objects.get(user=a, peer=b)
        self.assertTrue(cs.is_archived)
        self.assertIsNotNone(cs.archived_at)

    def test_toggle_missing_user_id(self):
        user = make_user('tp04')
        login(self.client, user)
        response = post_json(self.client, reverse('toggle_pin_api'), {'value': True})
        self.assertEqual(response.status_code, 400)


# =========================================================================
# set_disappearing_api / get_conversation_settings_api
# =========================================================================
class DisappearingMessagesTests(_MessageTestBase):
    def test_enable_disappearing(self):
        a = make_user('dm01_a')
        b = make_user('dm01_b')
        login(self.client, a)
        response = post_json(self.client, reverse('set_disappearing_api'), {
            'user_id': b.id, 'enabled': True, 'ttl_seconds': 3600,
        })
        self.assertEqual(response.status_code, 200)
        cs = ConversationSettings.objects.get(user=a, peer=b)
        self.assertTrue(cs.disappearing_enabled)
        self.assertEqual(cs.disappearing_ttl_seconds, 3600)

    def test_disappearing_rejects_invalid_ttl(self):
        a = make_user('dm02_a')
        b = make_user('dm02_b')
        login(self.client, a)
        # > 4 周
        response = post_json(self.client, reverse('set_disappearing_api'), {
            'user_id': b.id, 'enabled': True, 'ttl_seconds': 9999999,
        })
        self.assertEqual(response.status_code, 400)

    def test_get_conversation_settings(self):
        a = make_user('dm03_a')
        b = make_user('dm03_b')
        cs = ConversationSettings.objects.create(user=a, peer=b, is_pinned=True)
        login(self.client, a)
        body = parse(self.client.get(reverse('get_conversation_settings_api') + f'?user_id={b.id}'))
        self.assertTrue(body['settings']['is_pinned'])

    def test_disappearing_destroys_read_messages_over_ttl(self):
        a = make_user('dm04_a')
        b = make_user('dm04_b')
        # a 启用阅后即焚, ttl=0(立即)
        ConversationSettings.objects.create(
            user=a, peer=b, disappearing_enabled=True, disappearing_ttl_seconds=0,
        )
        m = Message.objects.create(
            sender=b, recipient=a, content='auto-burn', is_read=True, read_at=timezone.now() - timedelta(seconds=10),
        )
        login(self.client, a)
        # 触发 _apply_disappearing
        self.client.get(reverse('get_messages_api') + f'?user_id={b.id}')
        m.refresh_from_db()
        self.assertTrue(m.is_recalled)


# =========================================================================
# search_messages_api
# =========================================================================
class SearchMessagesApiTests(_MessageTestBase):
    def test_search_finds_matching(self):
        alice = make_user('sm01_a')
        bob = make_user('sm01_b')
        carol = make_user('sm01_c')
        Message.objects.create(sender=alice, recipient=bob, content='HelloWorldFoo', searchable_text='HelloWorldFoo')
        Message.objects.create(sender=carol, recipient=alice, content='OtherMessageBar', searchable_text='OtherMessageBar')
        login(self.client, alice)
        body = parse(self.client.get(reverse('search_messages_api') + '?q=HelloWorldFoo'))
        contents = {r['content'] for r in body['results']}
        self.assertIn('HelloWorldFoo', contents)
        self.assertNotIn('OtherMessageBar', contents)

    def test_search_below_min_length_returns_empty(self):
        user = make_user('sm02')
        login(self.client, user)
        body = parse(self.client.get(reverse('search_messages_api') + '?q=a'))
        self.assertEqual(body.get('results', []), [])


# =========================================================================
# export_conversation_api
# =========================================================================
class ExportConversationApiTests(_MessageTestBase):
    def test_export_returns_txt(self):
        a = make_user('ex01_a')
        b = make_user('ex01_b')
        Message.objects.create(sender=a, recipient=b, content='Line 1')
        Message.objects.create(sender=b, recipient=a, content='Line 2')
        login(self.client, a)
        response = self.client.get(reverse('export_conversation_api') + f'?user_id={b.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        body = response.content.decode('utf-8')
        self.assertIn('Line 1', body)
        self.assertIn('Line 2', body)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_export_missing_user_id(self):
        user = make_user('ex02')
        login(self.client, user)
        response = self.client.get(reverse('export_conversation_api'))
        self.assertEqual(response.status_code, 400)


# =========================================================================
# report_user_api
# =========================================================================
class ReportUserApiTests(_MessageTestBase):
    def test_report_user_success(self):
        a = make_user('rp01_a')
        b = make_user('rp01_b')
        login(self.client, a)
        response = post_json(self.client, reverse('report_user_api'), {
            'user_id': b.id, 'reason': 'spam', 'detail': '广告刷屏',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(MessageReport.objects.filter(reporter=a, reported_user=b, reason='spam').exists())

    def test_cannot_report_self(self):
        user = make_user('rp02')
        login(self.client, user)
        response = post_json(self.client, reverse('report_user_api'), {
            'user_id': user.id, 'reason': 'other',
        })
        self.assertEqual(response.status_code, 400)

    def test_report_invalid_reason(self):
        a = make_user('rp03_a')
        b = make_user('rp03_b')
        login(self.client, a)
        response = post_json(self.client, reverse('report_user_api'), {
            'user_id': b.id, 'reason': 'made_up_reason',
        })
        self.assertEqual(response.status_code, 400)

    def test_report_message_marks_was_reported(self):
        a = make_user('rp04_a')
        b = make_user('rp04_b')
        msg = Message.objects.create(sender=b, recipient=a, content='坏话')
        login(self.client, a)
        post_json(self.client, reverse('report_user_api'), {
            'user_id': b.id, 'message_id': msg.id, 'reason': 'abuse',
        })
        msg.refresh_from_db()
        self.assertTrue(msg.was_reported)

    def test_outsider_cannot_report_message(self):
        a = make_user('rp05_a')
        b = make_user('rp05_b')
        outsider = make_user('rp05_o')
        msg = Message.objects.create(sender=a, recipient=b, content='私聊内容')
        login(self.client, outsider)
        response = post_json(self.client, reverse('report_user_api'), {
            'user_id': a.id, 'message_id': msg.id, 'reason': 'spam',
        })
        self.assertEqual(response.status_code, 403)


# =========================================================================
# moderation_user_sanction_api
# =========================================================================
class ModerationUserSanctionApiTests(_MessageTestBase):
    def test_non_admin_cannot_manually_sanction_user(self):
        moderator = make_user('ms01_mod')
        target = make_user('ms01_target')
        login(self.client, moderator)

        response = post_json(self.client, reverse('moderation_user_sanction_api', args=[target.id]), {
            'type': 'mute_messages',
            'duration': '24h',
            'note': 'repeat violation',
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(UserSanction.objects.filter(user=target).exists())

    def test_manual_resanction_requires_report_context(self):
        admin = make_user('ms04_admin', is_superuser=True)
        target = make_user('ms04_target')
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_user_sanction_api', args=[target.id]), {
            'type': 'ban_login',
            'duration': '24h',
            'note': 'missing source report',
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserSanction.objects.filter(user=target).exists())

    def test_admin_can_manually_resanction_user_with_report_context(self):
        admin = make_user('ms02_admin', is_superuser=True)
        reporter = make_user('ms02_reporter')
        target = make_user('ms02_target')
        msg = Message.objects.create(sender=target, recipient=reporter, content='repeat abuse')
        report = MessageReport.objects.create(
            reporter=reporter,
            reported_user=target,
            message=msg,
            reason='abuse',
            status='resolved',
            handled_by=admin,
            resolved_at=timezone.now(),
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_user_sanction_api', args=[target.id]), {
            'type': 'mute_messages',
            'duration': '7d',
            'note': 'continued violation after revoke',
            'source_report_type': 'message',
            'source_report_id': report.id,
        })

        self.assertEqual(response.status_code, 200, response.content)
        sanction = UserSanction.objects.get(user=target, sanction_type='mute_messages')
        self.assertTrue(sanction.is_active)
        self.assertEqual(sanction.source_report_type, 'message')
        self.assertEqual(sanction.source_report_id, report.id)
        self.assertTrue(
            ModerationLog.objects.filter(
                report_type='message',
                report_id=report.id,
                target_user=target,
                action='manual:mute_7d',
            ).exists()
        )

    def test_manual_resanction_rejects_unrelated_report_context(self):
        admin = make_user('ms03_admin', is_superuser=True)
        author = make_user('ms03_author')
        reporter = make_user('ms03_reporter')
        note = Note.objects.create(author=author, title='note', content='content', is_public=True)
        comment = NoteComment.objects.create(note=note, author=author, content='bad comment')
        report = CommentReport.objects.create(
            comment=comment,
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
            status='removed',
            handled_by=admin,
            handled_at=timezone.now(),
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_user_sanction_api', args=[author.id]), {
            'type': 'mute_messages',
            'duration': '7d',
            'note': 'wrong manual sanction type',
            'source_report_type': 'comment',
            'source_report_id': report.id,
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserSanction.objects.filter(user=author, sanction_type='mute_messages').exists())

    def test_manual_resanction_rejects_user_outside_source_report(self):
        admin = make_user('ms05_admin', is_superuser=True)
        reporter = make_user('ms05_reporter')
        target = make_user('ms05_target')
        unrelated = make_user('ms05_unrelated')
        msg = Message.objects.create(sender=target, recipient=reporter, content='repeat abuse')
        report = MessageReport.objects.create(
            reporter=reporter,
            reported_user=target,
            message=msg,
            reason='abuse',
            status='resolved',
            handled_by=admin,
            resolved_at=timezone.now(),
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_user_sanction_api', args=[unrelated.id]), {
            'type': 'mute_messages',
            'duration': '7d',
            'note': 'wrong target user',
            'source_report_type': 'message',
            'source_report_id': report.id,
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserSanction.objects.filter(user=unrelated).exists())


# =========================================================================
# note/comment report moderation
# =========================================================================
class NoteAndCommentReportTests(_MessageTestBase):
    def test_logged_in_user_can_report_public_note(self):
        author = make_user('nr01_author')
        reporter = make_user('nr01_reporter')
        note = Note.objects.create(
            author=author,
            title='reported note',
            content='<p>bad article</p>',
            is_public=True,
        )
        login(self.client, reporter)

        response = post_json(self.client, reverse('note_report_api', args=[note.id]), {
            'reason': 'abuse',
            'detail': 'contains abuse',
        })

        self.assertEqual(response.status_code, 200, response.content)
        report = NoteReport.objects.get(note=note, reporter=reporter)
        self.assertEqual(report.reported_user, author)
        self.assertEqual(report.status, 'pending')

    def test_cannot_report_own_comment(self):
        author = make_user('cr01_author')
        note = Note.objects.create(author=author, title='note', content='content', is_public=True)
        comment = NoteComment.objects.create(note=note, author=author, content='my comment')
        login(self.client, author)

        response = post_json(self.client, reverse('note_comment_report_api', args=[comment.id]), {
            'reason': 'other',
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(CommentReport.objects.exists())

    def test_admin_can_take_down_reported_note_and_sanction_author(self):
        admin = make_user('nr02_admin', is_superuser=True)
        author = make_user('nr02_author')
        reporter = make_user('nr02_reporter')
        note = Note.objects.create(
            author=author,
            title='reported note',
            content='<p>bad article</p>',
            is_public=True,
        )
        report = NoteReport.objects.create(
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_resolve_api', args=['note', report.id]), {
            'decision': 'uphold',
            'remove_content': True,
            'sanctions': [{'target': 'reported', 'type': 'ban_login', 'duration': '24h'}],
            'note': 'article violates rules',
        })

        self.assertEqual(response.status_code, 200, response.content)
        note.refresh_from_db()
        report.refresh_from_db()
        self.assertFalse(note.is_public)
        self.assertEqual(report.status, 'removed')
        self.assertTrue(UserSanction.objects.filter(user=author, sanction_type='ban_login', source_report_type='note').exists())
        self.assertTrue(ModerationLog.objects.filter(report_type='note', report_id=report.id, action='remove_content').exists())

    def test_admin_can_delete_reported_comment(self):
        admin = make_user('cr02_admin', is_superuser=True)
        author = make_user('cr02_author')
        reporter = make_user('cr02_reporter')
        note = Note.objects.create(author=reporter, title='note', content='content', is_public=True)
        comment = NoteComment.objects.create(note=note, author=author, content='bad comment')
        report = CommentReport.objects.create(
            comment=comment,
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_resolve_api', args=['comment', report.id]), {
            'decision': 'uphold',
            'remove_content': True,
            'sanctions': [],
            'note': 'comment violates rules',
        })

        self.assertEqual(response.status_code, 200, response.content)
        report.refresh_from_db()
        self.assertEqual(report.status, 'removed')
        self.assertFalse(NoteComment.objects.filter(id=comment.id).exists())

    def test_admin_can_apply_contextual_bans(self):
        admin = make_user('nr03_admin', is_superuser=True)
        author = make_user('nr03_author')
        reporter = make_user('nr03_reporter')
        note = Note.objects.create(author=author, title='note', content='content', is_public=True)
        note_report = NoteReport.objects.create(
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
        )
        comment = NoteComment.objects.create(note=note, author=author, content='bad comment')
        comment_report = CommentReport.objects.create(
            comment=comment,
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_resolve_api', args=['note', note_report.id]), {
            'decision': 'uphold',
            'remove_content': False,
            'sanctions': [
                {'target': 'reported', 'type': 'ban_public_notes', 'duration': '7d'},
            ],
            'note': 'repeat violations',
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(UserSanction.objects.filter(user=author, sanction_type='ban_public_notes').exists())
        self.assertTrue(ModerationLog.objects.filter(report_type='note', report_id=note_report.id, action='ban_public_notes_7d').exists())

        response = post_json(self.client, reverse('moderation_resolve_api', args=['comment', comment_report.id]), {
            'decision': 'uphold',
            'remove_content': False,
            'sanctions': [
                {'target': 'reported', 'type': 'ban_comments', 'duration': '24h'},
            ],
            'note': 'comment violations',
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(UserSanction.objects.filter(user=author, sanction_type='ban_comments').exists())
        self.assertTrue(ModerationLog.objects.filter(report_type='comment', report_id=comment_report.id, action='ban_comments_24h').exists())

    def test_report_type_rejects_unrelated_sanction(self):
        admin = make_user('nr06_admin', is_superuser=True)
        author = make_user('nr06_author')
        reporter = make_user('nr06_reporter')
        note = Note.objects.create(author=reporter, title='note', content='content', is_public=True)
        comment = NoteComment.objects.create(note=note, author=author, content='bad comment')
        report = CommentReport.objects.create(
            comment=comment,
            note=note,
            reporter=reporter,
            reported_user=author,
            reason='abuse',
        )
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_resolve_api', args=['comment', report.id]), {
            'decision': 'uphold',
            'remove_content': False,
            'sanctions': [
                {'target': 'reported', 'type': 'ban_public_notes', 'duration': '7d'},
            ],
            'note': 'wrong sanction type',
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(UserSanction.objects.filter(user=author, sanction_type='ban_public_notes').exists())

    def test_note_report_captures_snapshot_and_notifies_reporter(self):
        author = make_user('nr07_author')
        reporter = make_user('nr07_reporter')
        note = Note.objects.create(
            author=author,
            title='snapshot title',
            content='<p>snapshot body</p>',
            is_public=True,
        )
        login(self.client, reporter)

        response = post_json(self.client, reverse('note_report_api', args=[note.id]), {
            'reason': 'privacy',
            'detail': 'contains private info',
        })

        self.assertEqual(response.status_code, 200, response.content)
        report = NoteReport.objects.get(note=note, reporter=reporter)
        self.assertEqual(report.evidence_snapshot['title'], 'snapshot title')
        self.assertIn('snapshot body', report.evidence_snapshot['content_preview'])
        self.assertTrue(UserNotification.objects.filter(user=reporter, kind='report_received').exists())

    def test_admin_resolve_merges_duplicate_pending_reports(self):
        admin = make_user('nr08_admin', is_superuser=True)
        author = make_user('nr08_author')
        reporter_a = make_user('nr08_reporter_a')
        reporter_b = make_user('nr08_reporter_b')
        note = Note.objects.create(author=author, title='duplicate note', content='content', is_public=True)
        first = NoteReport.objects.create(note=note, reporter=reporter_a, reported_user=author, reason='abuse')
        second = NoteReport.objects.create(note=note, reporter=reporter_b, reported_user=author, reason='spam')
        login(self.client, admin)

        response = post_json(self.client, reverse('moderation_resolve_api', args=['note', first.id]), {
            'decision': 'uphold',
            'remove_content': False,
            'resolve_related': True,
            'sanctions': [],
            'note': 'merged decision',
        })

        self.assertEqual(response.status_code, 200, response.content)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, 'removed')
        self.assertEqual(second.status, 'removed')
        self.assertTrue(ModerationLog.objects.filter(report_type='note', report_id=second.id, action='merged_resolve').exists())
        self.assertTrue(UserNotification.objects.filter(user=reporter_b, kind='report_resolved').exists())

    def test_admin_can_load_moderation_templates(self):
        admin = make_user('nr09_admin', is_superuser=True)
        ModerationTemplate.objects.create(
            title='note uphold template',
            report_type='note',
            decision='uphold',
            content='template body',
        )
        login(self.client, admin)

        response = self.client.get(reverse('moderation_templates_api'), {'type': 'note', 'decision': 'uphold'})

        self.assertEqual(response.status_code, 200, response.content)
        body = parse(response)
        self.assertTrue(any(t['title'] == 'note uphold template' for t in body['templates']))

    def test_user_can_appeal_and_admin_can_accept(self):
        admin = make_user('nr10_admin', is_superuser=True)
        user = make_user('nr10_user')
        sanction = UserSanction.objects.create(
            user=user,
            sanction_type='ban_comments',
            created_by=admin,
            source_report_type='comment',
            source_report_id=123,
        )
        login(self.client, user)

        response = post_json(self.client, reverse('moderation_sanction_appeal_api', args=[sanction.id]), {
            'reason': 'I think this was a mistake',
        })

        self.assertEqual(response.status_code, 200, response.content)
        appeal = ModerationAppeal.objects.get(sanction=sanction)
        self.assertTrue(UserNotification.objects.filter(user=user, kind='appeal_submitted').exists())

        login(self.client, admin)
        response = post_json(self.client, reverse('moderation_appeal_resolve_api', args=[appeal.id]), {
            'decision': 'accepted',
            'note': 'appeal accepted',
        })

        self.assertEqual(response.status_code, 200, response.content)
        appeal.refresh_from_db()
        sanction.refresh_from_db()
        self.assertEqual(appeal.status, 'accepted')
        self.assertFalse(sanction.is_active)
        self.assertTrue(UserNotification.objects.filter(user=user, kind='appeal_resolved').exists())

    def test_comment_ban_blocks_public_note_comments(self):
        author = make_user('nr04_author')
        commenter = make_user('nr04_commenter')
        note = Note.objects.create(author=author, title='note', content='content', is_public=True)
        UserSanction.objects.create(user=commenter, sanction_type='ban_comments', created_by=author)
        login(self.client, commenter)

        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]), {
            'content': 'blocked comment',
        })

        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(NoteComment.objects.filter(note=note, author=commenter).exists())

    def test_public_note_ban_blocks_publishing(self):
        user = make_user('nr05_user')
        note = Note.objects.create(author=user, title='note', content='content', is_public=False)
        UserSanction.objects.create(user=user, sanction_type='ban_public_notes')
        login(self.client, user)

        response = self.client.patch(
            reverse('api_note_detail', args=[note.id]),
            data=json.dumps({'is_public': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403, response.content)
        note.refresh_from_db()
        self.assertFalse(note.is_public)


# =========================================================================
# get_unread_messages_count_api
# =========================================================================
class UnreadCountApiTests(_MessageTestBase):
    def test_zero_unread(self):
        user = make_user('uc01')
        login(self.client, user)
        body = parse(self.client.get(reverse('get_unread_messages_count_api')))
        self.assertEqual(body.get('unread_count', 0), 0)

    def test_counts_only_unread(self):
        alice = make_user('uc02_a')
        bob = make_user('uc02_b')
        Message.objects.create(sender=bob, recipient=alice, content='r1', is_read=True)
        Message.objects.create(sender=bob, recipient=alice, content='u1', is_read=False)
        Message.objects.create(sender=bob, recipient=alice, content='u2', is_read=False)
        Message.objects.create(sender=alice, recipient=bob, content='out', is_read=False)
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_unread_messages_count_api')))
        self.assertEqual(body['unread_count'], 2)

    def test_excludes_deleted_for_recipient(self):
        alice = make_user('uc03_a')
        bob = make_user('uc03_b')
        Message.objects.create(sender=bob, recipient=alice, content='visible', is_read=False)
        Message.objects.create(
            sender=bob, recipient=alice, content='hidden',
            is_read=False, deleted_for_recipient=True,
        )
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_unread_messages_count_api')))
        self.assertEqual(body['unread_count'], 1)

    def test_excludes_recalled(self):
        alice = make_user('uc04_a')
        bob = make_user('uc04_b')
        Message.objects.create(sender=bob, recipient=alice, content='ok', is_read=False)
        Message.objects.create(sender=bob, recipient=alice, content='gone', is_read=False, is_recalled=True)
        login(self.client, alice)
        body = parse(self.client.get(reverse('get_unread_messages_count_api')))
        self.assertEqual(body['unread_count'], 1)


# =========================================================================
# get_message_preference_api / update_message_preference_api
# =========================================================================
class MessagePreferenceTests(_MessageTestBase):
    def test_get_default_preference(self):
        user = make_user('mp01')
        login(self.client, user)
        body = parse(self.client.get(reverse('get_message_preference_api')))
        self.assertIn(body['preference']['message_mode'],
                      ['all', 'followers_only', 'following_only', 'disabled'])

    def test_update_preference(self):
        user = make_user('mp02')
        login(self.client, user)
        response = post_json(self.client, reverse('update_message_preference_api'), {
            'message_mode': 'followers_only',
            'show_read_status': False,
        })
        self.assertEqual(response.status_code, 200)
        pref = MessagePreference.objects.get(user=user)
        self.assertEqual(pref.message_mode, 'followers_only')
        self.assertFalse(pref.show_read_status)

    def test_update_rejects_invalid_mode(self):
        user = make_user('mp03')
        login(self.client, user)
        post_json(self.client, reverse('update_message_preference_api'), {
            'message_mode': 'invalid_mode',
        })
        pref = MessagePreference.objects.get(user=user)
        self.assertNotEqual(pref.message_mode, 'invalid_mode')

    def test_update_truncates_auto_reply(self):
        user = make_user('mp04')
        login(self.client, user)
        long_text = 'x' * 1000
        post_json(self.client, reverse('update_message_preference_api'), {
            'auto_reply_enabled': True,
            'auto_reply_text': long_text,
        })
        pref = MessagePreference.objects.get(user=user)
        self.assertEqual(len(pref.auto_reply_text), 500)


# =========================================================================
# block_user_api / unblock_user_api / get_blocked_users_api
# =========================================================================
class BlockApiTests(_MessageTestBase):
    def test_block_user(self):
        a = make_user('bk01_a')
        b = make_user('bk01_b')
        login(self.client, a)
        response = post_json(self.client, reverse('block_user_api'), {
            'user_id': b.id, 'reason': 'spam',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserBlocklist.objects.filter(user=a, blocked_user=b).exists())

    def test_block_cannot_target_self(self):
        user = make_user('bk02')
        login(self.client, user)
        response = post_json(self.client, reverse('block_user_api'), {'user_id': user.id})
        self.assertEqual(response.status_code, 400)

    def test_block_missing_user_id(self):
        user = make_user('bk03')
        login(self.client, user)
        response = post_json(self.client, reverse('block_user_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_block_is_idempotent(self):
        a = make_user('bk04_a')
        b = make_user('bk04_b')
        UserBlocklist.objects.create(user=a, blocked_user=b, reason='first')
        login(self.client, a)
        response = post_json(self.client, reverse('block_user_api'), {
            'user_id': b.id, 'reason': 'updated',
        })
        self.assertEqual(response.status_code, 200)
        bl = UserBlocklist.objects.get(user=a, blocked_user=b)
        self.assertEqual(bl.reason, 'updated')

    def test_unblock_user(self):
        a = make_user('bk05_a')
        b = make_user('bk05_b')
        UserBlocklist.objects.create(user=a, blocked_user=b)
        login(self.client, a)
        response = post_json(self.client, reverse('unblock_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserBlocklist.objects.filter(user=a, blocked_user=b).exists())

    def test_unblock_missing_user_id(self):
        user = make_user('bk06')
        login(self.client, user)
        response = post_json(self.client, reverse('unblock_user_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_blocked_list(self):
        a = make_user('bk07_a')
        b = make_user('bk07_b')
        c = make_user('bk07_c')
        UserBlocklist.objects.create(user=a, blocked_user=b)
        UserBlocklist.objects.create(user=a, blocked_user=c)
        login(self.client, a)
        body = parse(self.client.get(reverse('get_blocked_users_api')))
        ids = {u['id'] for u in body['blocked_users']}
        self.assertEqual(ids, {b.id, c.id})


# =========================================================================
# get_user_public_profile_api
# =========================================================================
class UserPublicProfileApiTests(_MessageTestBase):
    def test_get_user_profile_basic(self):
        target = make_user('pp01_t')
        body = parse(self.client.get(reverse('get_user_public_profile_api', args=[target.id])))
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['id'], target.id)
        self.assertEqual(body['username'], target.username)
        self.assertIn('avatar', body)
        self.assertIn('public_notes_url', body)

    def test_get_user_profile_nonexistent_returns_404(self):
        response = self.client.get(reverse('get_user_public_profile_api', args=[9999999]))
        self.assertEqual(response.status_code, 404)


# =========================================================================
# search_users_api
# =========================================================================
class SearchUsersApiTests(_MessageTestBase):
    def test_short_query_returns_empty(self):
        body = parse(self.client.get(reverse('search_users_api') + '?q=ab'))
        self.assertEqual(body.get('users', []), [])

    def test_search_by_username_requires_discoverable(self):
        target = make_user('searchable_user')
        # 默认 discoverable_by_username=False -> 找不到
        body = parse(self.client.get(reverse('search_users_api') + '?q=searchable_user'))
        self.assertEqual(body.get('users', []), [])

        # 打开开关后能命中
        target.profile.discoverable_by_username = True
        target.profile.save(update_fields=['discoverable_by_username'])
        body = parse(self.client.get(reverse('search_users_api') + '?q=searchable_user'))
        self.assertEqual(len(body['users']), 1)
        self.assertEqual(body['users'][0]['id'], target.id)

    def test_cannot_search_self(self):
        user = make_user('selfsearch01')
        user.profile.discoverable_by_username = True
        user.profile.save(update_fields=['discoverable_by_username'])
        login(self.client, user)
        body = parse(self.client.get(reverse('search_users_api') + '?q=selfsearch01'))
        self.assertEqual(body.get('users', []), [])

    def test_search_by_search_code(self):
        target = make_user('codesearch01')
        target.profile.search_code = 'ABCD1234'
        target.profile.save(update_fields=['search_code'])
        body = parse(self.client.get(reverse('search_users_api') + '?q=ABCD1234'))
        self.assertEqual(len(body['users']), 1)
        self.assertEqual(body['users'][0]['matched_by'], 'code')


# =========================================================================
# update_discoverability_api
# =========================================================================
class DiscoverabilityApiTests(_MessageTestBase):
    def test_get_discoverability(self):
        user = make_user('dc01')
        login(self.client, user)
        body = parse(self.client.get(reverse('update_discoverability_api')))
        self.assertEqual(body['status'], 'success')
        self.assertIn('discoverable_by_username', body)
        self.assertIn('search_code', body)

    def test_update_discoverability(self):
        user = make_user('dc02')
        login(self.client, user)
        response = post_json(self.client, reverse('update_discoverability_api'), {
            'discoverable_by_username': True,
            'discoverable_by_email': True,
        })
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.discoverable_by_username)
        self.assertTrue(user.profile.discoverable_by_email)

    def test_regenerate_search_code(self):
        user = make_user('dc03')
        old_code = user.profile.search_code
        login(self.client, user)
        body = parse(post_json(self.client, reverse('update_discoverability_api'), {
            'regenerate_code': True,
        }))
        self.assertEqual(body['status'], 'success')
        new_code = body['search_code']
        self.assertEqual(len(new_code), 8)
        if old_code:
            self.assertNotEqual(new_code, old_code)


# =========================================================================
# touch_messages_page_api
# =========================================================================
class TouchMessagesPageTests(_MessageTestBase):
    def test_touch_updates_session(self):
        user = make_user('tm01')
        login(self.client, user)
        response = post_json(self.client, reverse('touch_messages_page_api'), {})
        self.assertEqual(response.status_code, 200)
        # session 中应该写了 messages_page_active_at
        self.assertIn('messages_page_active_at', self.client.session)


# =========================================================================
# 新对话配额(Turnstile) 限流分支
# =========================================================================
class NewConversationQuotaTests(_MessageTestBase):
    def test_quota_under_limit_does_not_require_turnstile(self):
        sender = make_user('nq01_s')
        recipient = make_user('nq01_r')
        _enable_messaging(recipient)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'first time',
        })
        self.assertEqual(response.status_code, 201)
        # 应该有配额日志记录
        self.assertTrue(NewConversationQuotaLog.objects.filter(user=sender, peer=recipient).exists())

    def test_quota_exceeded_requires_turnstile(self):
        sender = make_user('nq02_s')
        login(self.client, sender)
        # 创建 5 条已用配额日志(= NEW_CONV_DAILY_LIMIT)
        for i in range(5):
            peer = make_user(f'nq02_peer{i}')
            NewConversationQuotaLog.objects.create(user=sender, peer=peer)
        new_peer = make_user('nq02_new_peer')
        _enable_messaging(new_peer)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': new_peer.id,
            'content': 'hi',
        })
        self.assertEqual(response.status_code, 429)
        body = parse(response)
        self.assertTrue(body.get('need_turnstile'))

    def test_quota_exceeded_passes_with_valid_turnstile(self):
        sender = make_user('nq03_s')
        login(self.client, sender)
        for i in range(5):
            peer = make_user(f'nq03_peer{i}')
            NewConversationQuotaLog.objects.create(user=sender, peer=peer)
        new_peer = make_user('nq03_new_peer')
        _enable_messaging(new_peer)
        with patch('knowledge_project.utils.turnstile.verify_turnstile_token', return_value=True):
            response = post_json(self.client, reverse('send_message_api'), {
                'recipient_id': new_peer.id,
                'content': 'hi',
                'turnstile_token': 'fake-valid-token',
            })
        self.assertEqual(response.status_code, 201)
        # 应当记录 turnstile_passed=True
        log = NewConversationQuotaLog.objects.filter(user=sender, peer=new_peer).first()
        self.assertIsNotNone(log)
        self.assertTrue(log.turnstile_passed)

    def test_existing_conversation_skips_quota(self):
        sender = make_user('nq04_s')
        recipient = make_user('nq04_r')
        _enable_messaging(recipient)
        # 双方已有对话
        Message.objects.create(sender=recipient, recipient=sender, content='历史消息')
        # 用满 5 个其它新对话配额
        for i in range(5):
            peer = make_user(f'nq04_peer{i}')
            NewConversationQuotaLog.objects.create(user=sender, peer=peer)
        login(self.client, sender)
        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': recipient.id,
            'content': 'reply',
        })
        # 不算新对话,不应该 429
        self.assertEqual(response.status_code, 201)


# =========================================================================
# 附件上传 (无文件 / 无效类型)
# =========================================================================
class UploadAttachmentApiTests(_MessageTestBase):
    def test_upload_without_file_returns_400(self):
        user = make_user('ua01')
        login(self.client, user)
        response = self.client.post(reverse('upload_message_attachment_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_upload_unsupported_type_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = make_user('ua02')
        login(self.client, user)
        # text/html 不在白名单
        bad = SimpleUploadedFile('evil.html', b'<html></html>', content_type='text/html')
        response = self.client.post(reverse('upload_message_attachment_api'), {'file': bad})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MessageAttachment.objects.filter(uploader=user).exists())
