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
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from messaging.models import (
    ConversationSettings,
    DirectMessageMute,
    DirectNoteShare,
    DirectNoteShareRead,
    GroupMessage,
    GroupMessageMention,
    GroupNoteShare,
    GroupNoteShareRead,
    GroupPoll,
    GroupTask,
    Message,
    MessageAttachment,
    MessageGroup,
    MessageGroupAnnouncementHistory,
    MessageGroupAnnouncementRead,
    MessageGroupAuditLog,
    MessageGroupBan,
    MessageGroupInviteLink,
    MessageGroupInviteUse,
    MessageGroupMember,
    MessageGroupPolicy,
    GroupJoinRequest,
    MessagePreference,
    NewConversationQuotaLog,
    UserBlocklist,
    UserFollow,
)
from moderation.models import (
    CommentReport,
    MessageReport,
    ModerationAppeal,
    ModerationLog,
    ModerationTemplate,
    NoteReport,
    UserSanction,
)
from notes.models import Note, NoteComment
from notifications.models import UserNotification

from ._helpers import login, make_user, parse, post_json


def _enable_messaging(user, mode: str = 'all') -> MessagePreference:
    """打开 user 的接收开关。signal 已创建过 pref,这里走 update 路径。"""
    pref, _ = MessagePreference.objects.get_or_create(user=user)
    pref.allow_messages = True
    pref.message_mode = mode
    pref.save()
    return pref


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    # Tests call Django directly rather than through the HTTPS reverse proxy.
    SECURE_SSL_REDIRECT=False,
)
class _MessageTestBase(TestCase):
    def setUp(self):
        cache.clear()


class MessagePageTests(_MessageTestBase):
    def test_messages_page_versions_shared_dialog_styles_with_the_message_bundle(self):
        user = make_user('messages-page-user')
        login(self.client, user)

        response = self.client.get(reverse('messages'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        versions = re.findall(r'dist/(?:messages\.js|assets/(?:messages|index2)\.css)\?v=([0-9a-f]{20})', html)
        self.assertEqual(len(versions), 3)
        self.assertEqual(len(set(versions)), 1)


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


    def test_sender_can_edit_private_message_inline(self):
        sender = make_user('snd_edit_s')
        recipient = make_user('snd_edit_r')
        message = Message.objects.create(sender=sender, recipient=recipient, content='old private')
        login(self.client, sender)

        response = post_json(self.client, reverse('edit_message_api', args=[message.id]), {
            'content': 'new private',
        })

        self.assertEqual(response.status_code, 200, response.content)
        message.refresh_from_db()
        self.assertEqual(message.content, 'new private')
        self.assertTrue(message.is_edited)
        self.assertIsNotNone(message.edited_at)
        body = parse(response)
        self.assertEqual(body['message']['content'], 'new private')
        self.assertTrue(body['message']['is_edited'])

    def test_recipient_cannot_edit_private_message(self):
        sender = make_user('snd_edit_forbidden_s')
        recipient = make_user('snd_edit_forbidden_r')
        message = Message.objects.create(sender=sender, recipient=recipient, content='locked')
        login(self.client, recipient)

        response = post_json(self.client, reverse('edit_message_api', args=[message.id]), {
            'content': 'changed',
        })

        self.assertEqual(response.status_code, 403, response.content)
        message.refresh_from_db()
        self.assertEqual(message.content, 'locked')

    def test_sender_can_share_private_note_to_direct_message(self):
        sender = make_user('snd_note_share_s')
        recipient = make_user('snd_note_share_r')
        outsider = make_user('snd_note_share_o')
        _enable_messaging(recipient)
        note = Note.objects.create(
            author=sender,
            title='direct private note',
            content='<p>direct body</p>',
            is_public=False,
        )

        login(self.client, sender)
        response = post_json(self.client, reverse('share_note_to_user_api'), {
            'note_id': note.id,
            'recipient_id': recipient.id,
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['note_share']['title'], 'direct private note')
        share = DirectNoteShare.objects.get(note=note, recipient=recipient)

        self.client.logout()
        login(self.client, recipient)
        read_response = self.client.get(reverse('get_direct_note_share_api', args=[share.id]))
        self.assertEqual(read_response.status_code, 200, read_response.content)
        self.assertEqual(parse(read_response)['note']['content'], '<p>direct body</p>')

        self.client.logout()
        login(self.client, outsider)
        forbidden = self.client.get(reverse('get_direct_note_share_api', args=[share.id]))
        self.assertEqual(forbidden.status_code, 403, forbidden.content)

    def test_secret_note_cannot_be_shared_to_direct_message(self):
        sender = make_user('snd_secret_note_s')
        recipient = make_user('snd_secret_note_r')
        _enable_messaging(recipient)
        note = Note.objects.create(
            author=sender,
            title='secret direct note',
            content='encrypted',
            is_secret=True,
        )

        login(self.client, sender)
        response = post_json(self.client, reverse('share_note_to_user_api'), {
            'note_id': note.id,
            'recipient_id': recipient.id,
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(DirectNoteShare.objects.filter(note=note).exists())

    def test_sender_can_list_and_revoke_direct_note_shares(self):
        sender = make_user('snd_share_center_s')
        recipient = make_user('snd_share_center_r')
        outsider = make_user('snd_share_center_o')
        note = Note.objects.create(author=sender, title='direct center note', content='body')
        message = Message.objects.create(sender=sender, recipient=recipient, content='shared note')
        share = DirectNoteShare.objects.create(
            message=message,
            note=note,
            shared_by=sender,
            recipient=recipient,
            title_snapshot=note.title,
        )
        login(self.client, sender)

        list_body = parse(self.client.get(f"{reverse('list_note_shares_api')}?scope=direct"))
        self.assertEqual(list_body['shares'][0]['scope'], 'direct')
        self.assertEqual(list_body['shares'][0]['note']['title'], 'direct center note')
        self.assertEqual(list_body['shares'][0]['target']['id'], recipient.id)

        response = post_json(
            self.client,
            reverse('revoke_note_share_api', args=['direct', share.id]),
            {},
        )
        self.assertEqual(response.status_code, 200, response.content)
        share.refresh_from_db()
        self.assertIsNotNone(share.revoked_at)
        self.assertTrue(parse(response)['share']['is_revoked'])

        self.client.logout()
        login(self.client, outsider)
        forbidden = post_json(
            self.client,
            reverse('revoke_note_share_api', args=['direct', share.id]),
            {},
        )
        self.assertEqual(forbidden.status_code, 404, forbidden.content)

    def test_direct_note_share_tracks_recipient_read_and_owner_manages_forwarding(self):
        sender = make_user('snd_share_read_sender')
        recipient = make_user('snd_share_read_recipient')
        _enable_messaging(recipient)
        note = Note.objects.create(author=sender, title='read tracking note', content='body')

        login(self.client, sender)
        shared = post_json(self.client, reverse('share_note_to_user_api'), {
            'note_id': note.id,
            'recipient_id': recipient.id,
        })
        self.assertEqual(shared.status_code, 201, shared.content)
        share = DirectNoteShare.objects.get(note=note, recipient=recipient)

        own_read = self.client.get(reverse('get_direct_note_share_api', args=[share.id]))
        self.assertEqual(own_read.status_code, 200, own_read.content)
        self.assertFalse(DirectNoteShareRead.objects.filter(share=share).exists())

        self.client.logout()
        login(self.client, recipient)
        read = self.client.get(reverse('get_direct_note_share_api', args=[share.id]))
        self.assertEqual(read.status_code, 200, read.content)
        second_read = self.client.get(reverse('get_direct_note_share_api', args=[share.id]))
        self.assertEqual(second_read.status_code, 200, second_read.content)
        self.assertTrue(DirectNoteShareRead.objects.filter(share=share, reader=recipient).exists())

        self.client.logout()
        login(self.client, sender)
        reads = self.client.get(reverse('list_note_share_reads_api', args=['direct', share.id]))
        self.assertEqual(reads.status_code, 200, reads.content)
        self.assertEqual(parse(reads)['read_count'], 1)
        self.assertEqual(parse(reads)['view_count'], 2)
        self.assertEqual(parse(reads)['reads'][0]['view_count'], 2)
        self.assertEqual(parse(reads)['reads'][0]['user']['id'], recipient.id)

        update = post_json(
            self.client,
            reverse('update_note_share_forwarding_api', args=['direct', share.id]),
            {'allow_forwarding': False},
        )
        self.assertEqual(update.status_code, 200, update.content)
        share.refresh_from_db()
        self.assertFalse(share.allow_forwarding)
        self.assertFalse(parse(update)['share']['allow_forwarding'])

    def test_direct_note_share_prohibits_forwarding(self):
        sender = make_user('snd_share_fwd_sender')
        recipient = make_user('snd_share_fwd_recipient')
        target = make_user('snd_share_fwd_target')
        _enable_messaging(recipient)
        _enable_messaging(target)
        note = Note.objects.create(author=sender, title='no forward direct', content='body')
        message = Message.objects.create(sender=sender, recipient=recipient, content='[笔记] no forward direct')
        DirectNoteShare.objects.create(
            message=message,
            note=note,
            shared_by=sender,
            recipient=recipient,
            title_snapshot=note.title,
            allow_forwarding=False,
        )

        login(self.client, recipient)
        response = post_json(self.client, reverse('forward_message_api'), {
            'message_id': message.id,
            'recipient_id': target.id,
        })
        self.assertEqual(response.status_code, 403, response.content)

    def test_forwarded_direct_note_share_remains_note_card(self):
        sender = make_user('snd_share_card_sender')
        recipient = make_user('snd_share_card_recipient')
        target = make_user('snd_share_card_target')
        _enable_messaging(recipient)
        _enable_messaging(target)
        note = Note.objects.create(author=sender, title='forwarded direct card', content='body')
        source_message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content='[笔记] forwarded direct card',
        )
        DirectNoteShare.objects.create(
            message=source_message,
            note=note,
            shared_by=sender,
            recipient=recipient,
            title_snapshot=note.title,
        )

        login(self.client, recipient)
        response = post_json(self.client, reverse('forward_message_api'), {
            'message_id': source_message.id,
            'recipient_id': target.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['note_share']['title'], note.title)
        forwarded_share = DirectNoteShare.objects.get(message_id=body['message']['id'])
        self.assertEqual(forwarded_share.note_id, note.id)
        self.assertEqual(forwarded_share.shared_by_id, recipient.id)
        self.assertEqual(forwarded_share.recipient_id, target.id)


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

    def _enable_2fa(self, user):
        user.profile.two_fa_enabled = True
        user.profile.two_fa_method = 'totp'
        user.profile.save(update_fields=['two_fa_enabled', 'two_fa_method'])

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
        self.assertTrue(policy['two_fa_required'])
        self.assertFalse(policy['two_fa_enabled'])
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

    def test_user_missing_followers_cannot_create_group_even_with_required_public_notes(self):
        owner = make_user('grp_notes_owner')
        member = make_user('grp_notes_member')
        self._make_public_notes(owner, 10)
        self._enable_2fa(owner)
        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'notes group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 403)
        policy = parse(response)['policy']
        self.assertTrue(policy['reasons']['public_notes'])
        self.assertFalse(policy['reasons']['followers'])
        self.assertFalse(MessageGroup.objects.exists())

    def test_user_meeting_public_notes_and_followers_can_create_group(self):
        owner = make_user('grp_follow_owner')
        member = make_user('grp_follow_member')
        MessageGroupPolicy.objects.create(min_public_notes=3, min_followers=2)
        self._make_public_notes(owner, 3)
        self._enable_2fa(owner)
        for i in range(2):
            follower = make_user(f'grp_follow_follower_{i}')
            UserFollow.objects.create(follower=follower, following=owner)

        login(self.client, owner)
        response = post_json(self.client, reverse('create_message_group_api'), {
            'name': 'followers group',
            'member_ids': [member.id],
        })
        self.assertEqual(response.status_code, 201, response.content)
        group = MessageGroup.objects.get(name='followers group')
        self.assertEqual(group.owner, owner)
        self.assertEqual(group.memberships.filter(left_at__isnull=True).count(), 2)

    def test_disabled_group_policy_blocks_creation_even_when_threshold_met(self):
        owner = make_user('grp_disabled_owner')
        member = make_user('grp_disabled_member')
        self._make_public_notes(owner, 10)
        self._enable_2fa(owner)
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

    def test_group_message_cannot_forward_message_from_invisible_group(self):
        owner = make_user('grp_forward_owner')
        member = make_user('grp_forward_member')
        other_owner = make_user('grp_forward_other_owner')
        group = self._create_group_directly(owner, [member])
        other_group = self._create_group_directly(other_owner, [])
        source_message = GroupMessage.objects.create(
            group=other_group,
            sender=other_owner,
            content='hidden source',
        )

        login(self.client, member)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'forward attempt',
            'forwarded_from': source_message.id,
        })

        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(GroupMessage.objects.filter(group=group, content='forward attempt').exists())

    def test_group_message_can_forward_to_private_user(self):
        owner = make_user('grp_forward_private_owner')
        member = make_user('grp_forward_private_member')
        recipient = make_user('grp_forward_private_recipient')
        _enable_messaging(recipient)
        group = self._create_group_directly(owner, [member])
        source_message = GroupMessage.objects.create(
            group=group,
            sender=owner,
            content='group source text',
        )

        login(self.client, member)
        response = post_json(self.client, reverse('forward_message_api'), {
            'group_message_id': source_message.id,
            'recipient_id': recipient.id,
            'content': 'forwarded from group',
        })

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Message.objects.filter(
            sender=member,
            recipient=recipient,
            content='forwarded from group',
        ).exists())

    def test_group_note_card_forwarded_to_private_user_remains_note_card(self):
        owner = make_user('grp_forward_note_owner')
        member = make_user('grp_forward_note_member')
        recipient = make_user('grp_forward_note_recipient')
        _enable_messaging(recipient)
        group = self._create_group_directly(owner, [member])
        note = Note.objects.create(author=owner, title='group forwarded card', content='body')
        source_message = GroupMessage.objects.create(
            group=group,
            sender=owner,
            content='[笔记] group forwarded card',
        )
        GroupNoteShare.objects.create(
            group=group,
            message=source_message,
            note=note,
            shared_by=owner,
            title_snapshot=note.title,
        )

        login(self.client, member)
        response = post_json(self.client, reverse('forward_message_api'), {
            'group_message_id': source_message.id,
            'recipient_id': recipient.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['note_share']['title'], note.title)
        forwarded_share = DirectNoteShare.objects.get(message_id=body['message']['id'])
        self.assertEqual(forwarded_share.note_id, note.id)
        self.assertEqual(forwarded_share.shared_by_id, member.id)
        self.assertEqual(forwarded_share.recipient_id, recipient.id)

    def test_group_note_card_forwarded_to_group_remains_note_card(self):
        owner = make_user('grp_forward_note_group_owner')
        member = make_user('grp_forward_note_group_member')
        target_owner = make_user('grp_forward_note_target_owner')
        source_group = self._create_group_directly(owner, [member])
        target_group = self._create_group_directly(target_owner, [member])
        note = Note.objects.create(author=owner, title='cross group note card', content='body')
        source_message = GroupMessage.objects.create(
            group=source_group,
            sender=owner,
            content='[笔记] cross group note card',
        )
        GroupNoteShare.objects.create(
            group=source_group,
            message=source_message,
            note=note,
            shared_by=owner,
            title_snapshot=note.title,
        )

        login(self.client, member)
        response = post_json(self.client, reverse('send_group_message_api', args=[target_group.id]), {
            'content': source_message.content,
            'forwarded_from': source_message.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['note_share']['title'], note.title)
        forwarded_share = GroupNoteShare.objects.get(message_id=body['message']['id'])
        self.assertEqual(forwarded_share.group_id, target_group.id)
        self.assertEqual(forwarded_share.note_id, note.id)
        self.assertEqual(forwarded_share.shared_by_id, member.id)

    def test_private_message_can_forward_to_group(self):
        sender = make_user('private_forward_sender')
        recipient = make_user('private_forward_recipient')
        group_owner = make_user('private_forward_group_owner')
        group = self._create_group_directly(group_owner, [sender])
        source_message = Message.objects.create(
            sender=recipient,
            recipient=sender,
            content='private source text',
        )

        login(self.client, sender)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': 'forwarded from private',
            'forwarded_private_from': source_message.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(GroupMessage.objects.filter(
            group=group,
            sender=sender,
            content='forwarded from private',
        ).exists())

    def test_direct_note_card_forwarded_to_group_remains_note_card(self):
        sender = make_user('direct_forward_note_sender')
        recipient = make_user('direct_forward_note_recipient')
        group_owner = make_user('direct_forward_note_group_owner')
        group = self._create_group_directly(group_owner, [recipient])
        note = Note.objects.create(author=sender, title='direct to group card', content='body')
        source_message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content='[笔记] direct to group card',
        )
        DirectNoteShare.objects.create(
            message=source_message,
            note=note,
            shared_by=sender,
            recipient=recipient,
            title_snapshot=note.title,
        )

        login(self.client, recipient)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': source_message.content,
            'forwarded_private_from': source_message.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['note_share']['title'], note.title)
        forwarded_share = GroupNoteShare.objects.get(message_id=body['message']['id'])
        self.assertEqual(forwarded_share.group_id, group.id)
        self.assertEqual(forwarded_share.note_id, note.id)
        self.assertEqual(forwarded_share.shared_by_id, recipient.id)

    def test_private_note_shared_to_group_requires_current_group_membership(self):
        owner = make_user('grp_note_share_owner')
        member = make_user('grp_note_share_member')
        outsider = make_user('grp_note_share_outsider')
        group = self._create_group_directly(owner, [member])
        note = Note.objects.create(
            author=owner,
            title='private group note',
            content='<p>group-only body</p>',
            is_public=False,
        )

        login(self.client, owner)
        response = post_json(self.client, reverse('share_note_to_group_api', args=[group.id]), {
            'note_id': note.id,
        })
        self.assertEqual(response.status_code, 201, response.content)
        message_body = parse(response)['message']
        self.assertEqual(message_body['note_share']['title'], 'private group note')
        self.assertTrue(message_body['note_share']['requires_group_membership'])
        share = GroupNoteShare.objects.get(note=note, group=group)

        self.client.logout()
        login(self.client, member)
        read_response = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(read_response.status_code, 200, read_response.content)
        read_body = parse(read_response)
        self.assertEqual(read_body['note']['content'], '<p>group-only body</p>')
        self.assertFalse(read_body['note']['is_public'])

        self.client.logout()
        login(self.client, outsider)
        outsider_response = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(outsider_response.status_code, 403, outsider_response.content)

        MessageGroupMember.objects.filter(group=group, user=member).update(left_at=timezone.now())
        self.client.logout()
        login(self.client, member)
        former_member_response = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(former_member_response.status_code, 403, former_member_response.content)

    def test_group_note_share_respects_history_visibility(self):
        owner = make_user('grp_note_history_owner')
        late_member = make_user('grp_note_history_member')
        group = self._create_group_directly(owner, [])
        note = Note.objects.create(
            author=owner,
            title='old private note',
            content='old private body',
            is_public=False,
        )

        login(self.client, owner)
        response = post_json(self.client, reverse('share_note_to_group_api', args=[group.id]), {
            'note_id': note.id,
        })
        self.assertEqual(response.status_code, 201, response.content)
        share = GroupNoteShare.objects.get(note=note, group=group)
        old_time = timezone.now() - timedelta(hours=2)
        GroupMessage.objects.filter(pk=share.message_id).update(created_at=old_time)
        MessageGroupMember.objects.create(group=group, user=late_member, role='member')

        self.client.logout()
        login(self.client, late_member)
        response = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(response.status_code, 403, response.content)

    def test_secret_note_cannot_be_shared_to_group_chat(self):
        owner = make_user('grp_secret_note_owner')
        member = make_user('grp_secret_note_member')
        group = self._create_group_directly(owner, [member])
        note = Note.objects.create(
            author=owner,
            title='vault note',
            content='encrypted body',
            is_secret=True,
        )

        login(self.client, owner)
        response = post_json(self.client, reverse('share_note_to_group_api', args=[group.id]), {
            'note_id': note.id,
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(GroupNoteShare.objects.filter(note=note).exists())

    def test_owner_can_list_and_revoke_group_note_shares(self):
        owner = make_user('grp_share_center_owner')
        member = make_user('grp_share_center_member')
        outsider = make_user('grp_share_center_outsider')
        group = self._create_group_directly(owner, [member])
        note = Note.objects.create(author=owner, title='group center note', content='body')
        message = GroupMessage.objects.create(group=group, sender=owner, content='shared group note')
        share = GroupNoteShare.objects.create(
            group=group,
            message=message,
            note=note,
            shared_by=owner,
            title_snapshot=note.title,
        )
        login(self.client, owner)

        list_body = parse(self.client.get(f"{reverse('list_note_shares_api')}?scope=group"))
        self.assertEqual(list_body['shares'][0]['scope'], 'group')
        self.assertEqual(list_body['shares'][0]['note']['title'], 'group center note')
        self.assertEqual(list_body['shares'][0]['target']['id'], group.id)

        response = post_json(
            self.client,
            reverse('revoke_note_share_api', args=['group', share.id]),
            {},
        )
        self.assertEqual(response.status_code, 200, response.content)
        share.refresh_from_db()
        self.assertIsNotNone(share.revoked_at)
        self.assertTrue(parse(response)['share']['is_revoked'])

        self.client.logout()
        login(self.client, outsider)
        forbidden = post_json(
            self.client,
            reverse('revoke_note_share_api', args=['group', share.id]),
            {},
        )
        self.assertEqual(forbidden.status_code, 404, forbidden.content)

    def test_group_note_share_tracks_member_read_and_prohibits_forwarding(self):
        owner = make_user('grp_share_read_owner')
        member = make_user('grp_share_read_member')
        recipient = make_user('grp_share_read_recipient')
        _enable_messaging(recipient)
        group = self._create_group_directly(owner, [member])
        note = Note.objects.create(author=owner, title='group read tracking note', content='body')

        login(self.client, owner)
        shared = post_json(self.client, reverse('share_note_to_group_api', args=[group.id]), {
            'note_id': note.id,
        })
        self.assertEqual(shared.status_code, 201, shared.content)
        share = GroupNoteShare.objects.get(note=note, group=group)

        own_read = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(own_read.status_code, 200, own_read.content)
        self.assertFalse(GroupNoteShareRead.objects.filter(share=share).exists())

        disable_forwarding = post_json(
            self.client,
            reverse('update_note_share_forwarding_api', args=['group', share.id]),
            {'allow_forwarding': False},
        )
        self.assertEqual(disable_forwarding.status_code, 200, disable_forwarding.content)
        self.assertFalse(parse(disable_forwarding)['share']['allow_forwarding'])

        self.client.logout()
        login(self.client, member)
        read = self.client.get(reverse('get_group_note_share_api', args=[group.id, share.id]))
        self.assertEqual(read.status_code, 200, read.content)
        self.assertTrue(GroupNoteShareRead.objects.filter(share=share, reader=member).exists())

        blocked_forward = post_json(self.client, reverse('forward_message_api'), {
            'group_message_id': share.message_id,
            'recipient_id': recipient.id,
        })
        self.assertEqual(blocked_forward.status_code, 403, blocked_forward.content)

        self.client.logout()
        login(self.client, owner)
        reads = self.client.get(reverse('list_note_share_reads_api', args=['group', share.id]))
        self.assertEqual(reads.status_code, 200, reads.content)
        self.assertEqual(parse(reads)['read_count'], 1)

    def test_group_messages_support_latest_page_pagination(self):
        owner = make_user('grp_page_owner')
        member = make_user('grp_page_member')
        group = self._create_group_directly(owner, [member])
        for i in range(5):
            GroupMessage.objects.create(group=group, sender=owner, content=f'group page {i}')

        login(self.client, member)
        url = reverse('get_group_messages_api', args=[group.id])
        first_page = parse(self.client.get(f'{url}?limit=2'))
        self.assertEqual([m['content'] for m in first_page['messages']], ['group page 3', 'group page 4'])
        self.assertTrue(first_page['pagination']['has_more'])
        self.assertEqual(first_page['pagination']['next_offset'], 2)

        second_page = parse(self.client.get(f'{url}?limit=2&offset=2'))
        self.assertEqual([m['content'] for m in second_page['messages']], ['group page 1', 'group page 2'])
        self.assertTrue(second_page['pagination']['has_more'])

    def test_group_message_search_filters_respect_visibility(self):
        owner = make_user('grp_search_owner')
        member = make_user('grp_search_member')
        other = make_user('grp_search_other')
        group = self._create_group_directly(owner, [member, other])
        group.allow_new_members_view_history = True
        group.save(update_fields=['allow_new_members_view_history'])
        target_date = timezone.localdate() - timedelta(days=1)
        target_created_at = timezone.make_aware(
            datetime.combine(target_date, datetime.min.time()) + timedelta(hours=12)
        )
        target = GroupMessage.objects.create(group=group, sender=owner, content='release checklist')
        GroupMessage.objects.filter(pk=target.pk).update(created_at=target_created_at)
        other_message = GroupMessage.objects.create(group=group, sender=other, content='release checklist')
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=target,
            file=SimpleUploadedFile('checklist.txt', b'checklist', content_type='text/plain'),
            original_name='checklist.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=9,
        )

        login(self.client, member)
        url = reverse('get_group_messages_api', args=[group.id])
        response = self.client.get(
            f'{url}?q=release&sender_id={owner.id}&date_from={target_date}'
            f'&date_to={target_date}&has_attachment=1'
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['id'] for item in parse(response)['messages']], [target.id])

        invalid_date = self.client.get(f'{url}?date_from=2026-99-99')
        self.assertEqual(invalid_date.status_code, 400, invalid_date.content)
        self.assertEqual(other_message.sender_id, other.id)

    def test_group_message_search_filters_cannot_reveal_pre_join_history(self):
        owner = make_user('grp_search_history_owner')
        member = make_user('grp_search_history_member')
        group = MessageGroup.objects.create(name='search history', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        now = timezone.now()
        hidden = GroupMessage.objects.create(group=group, sender=owner, content='prejoin restricted keyword')
        visible = GroupMessage.objects.create(group=group, sender=owner, content='afterjoin restricted keyword')
        GroupMessage.objects.filter(pk=hidden.pk).update(created_at=now - timedelta(hours=2))
        GroupMessage.objects.filter(pk=visible.pk).update(created_at=now - timedelta(minutes=10))
        membership = MessageGroupMember.objects.create(group=group, user=member, role='member')
        MessageGroupMember.objects.filter(pk=membership.pk).update(joined_at=now - timedelta(hours=1))

        login(self.client, member)
        url = reverse('get_group_messages_api', args=[group.id])
        response = self.client.get(f'{url}?q=restricted&sender_id={owner.id}')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['id'] for item in parse(response)['messages']], [visible.id])

    def test_new_members_cannot_view_pre_join_history_by_default(self):
        owner = make_user('grp_hist_owner')
        member = make_user('grp_hist_member')
        group = MessageGroup.objects.create(name='history default', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        now = timezone.now()
        old_message = GroupMessage.objects.create(group=group, sender=owner, content='before join')
        new_message = GroupMessage.objects.create(group=group, sender=owner, content='after join')
        GroupMessage.objects.filter(pk=old_message.pk).update(created_at=now - timedelta(hours=2))
        GroupMessage.objects.filter(pk=new_message.pk).update(created_at=now - timedelta(minutes=10))
        attachment = MessageAttachment.objects.create(
            uploader=owner,
            group_message=old_message,
            file=SimpleUploadedFile('old.txt', b'old', content_type='text/plain'),
            original_name='old.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=3,
        )
        membership = MessageGroupMember.objects.create(group=group, user=member, role='member')
        MessageGroupMember.objects.filter(pk=membership.pk).update(joined_at=now - timedelta(hours=1))

        login(self.client, member)
        conversations = parse(self.client.get(reverse('get_message_conversations_api')))['conversations']
        conversation = next(item for item in conversations if item.get('group_id') == group.id)
        self.assertEqual(conversation['last_message'], 'after join')
        self.assertEqual(conversation['unread_count'], 1)

        list_body = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))
        self.assertEqual([message['content'] for message in list_body['messages']], ['after join'])

        file_response = self.client.get(reverse('message_attachment_file_api', args=[attachment.id]))
        self.assertEqual(file_response.status_code, 403, file_response.content)
        report_response = post_json(
            self.client,
            reverse('report_group_message_api', args=[group.id, old_message.id]),
            {'reason': 'abuse'},
        )
        self.assertEqual(report_response.status_code, 404)

    def test_group_setting_allows_new_members_to_view_history_without_unread_backfill(self):
        owner = make_user('grp_hist_on_owner')
        member = make_user('grp_hist_on_member')
        group = MessageGroup.objects.create(
            name='history enabled',
            owner=owner,
            created_by=owner,
            allow_new_members_view_history=True,
        )
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        now = timezone.now()
        old_message = GroupMessage.objects.create(group=group, sender=owner, content='before enabled join')
        new_message = GroupMessage.objects.create(group=group, sender=owner, content='after enabled join')
        GroupMessage.objects.filter(pk=old_message.pk).update(created_at=now - timedelta(hours=2))
        GroupMessage.objects.filter(pk=new_message.pk).update(created_at=now - timedelta(minutes=10))
        membership = MessageGroupMember.objects.create(group=group, user=member, role='member')
        MessageGroupMember.objects.filter(pk=membership.pk).update(joined_at=now - timedelta(hours=1))

        login(self.client, member)
        conversations = parse(self.client.get(reverse('get_message_conversations_api')))['conversations']
        conversation = next(item for item in conversations if item.get('group_id') == group.id)
        self.assertEqual(conversation['last_message'], 'after enabled join')
        self.assertEqual(conversation['unread_count'], 1)

        list_body = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))
        self.assertTrue(list_body['group']['allow_new_members_view_history'])
        self.assertEqual(
            [message['content'] for message in list_body['messages']],
            ['before enabled join', 'after enabled join'],
        )

    def test_group_message_can_send_and_serve_attachments(self):
        owner = make_user('grp_attach_owner')
        member = make_user('grp_attach_member')
        outsider = make_user('grp_attach_outsider')
        group = self._create_group_directly(owner, [member])
        attachment = MessageAttachment.objects.create(
            uploader=owner,
            file=SimpleUploadedFile('group-note.txt', b'hello group file', content_type='text/plain'),
            original_name='group-note.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=16,
        )

        login(self.client, owner)
        response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': '',
            'attachment_ids': [attachment.id],
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = parse(response)
        self.assertEqual(body['message']['attachments'][0]['id'], attachment.id)
        attachment.refresh_from_db()
        self.assertIsNone(attachment.message_id)
        self.assertIsNotNone(attachment.group_message_id)

        self.client.logout()
        login(self.client, member)
        list_body = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))
        self.assertEqual(list_body['messages'][0]['attachments'][0]['id'], attachment.id)
        file_response = self.client.get(reverse('message_attachment_file_api', args=[attachment.id]))
        self.assertEqual(file_response.status_code, 200)
        self.assertTrue(file_response.streaming)
        self.assertIn('attachment', file_response['Content-Disposition'])

        self.client.logout()
        login(self.client, outsider)
        forbidden = self.client.get(reverse('message_attachment_file_api', args=[attachment.id]))
        self.assertEqual(forbidden.status_code, 403, forbidden.content)

    def test_my_message_attachments_lists_own_direct_and_group_uploads(self):
        uploader = make_user('att_mine_owner')
        peer = make_user('att_mine_peer')
        other = make_user('att_mine_other')
        group = self._create_group_directly(uploader, [peer])
        direct_message = Message.objects.create(sender=uploader, recipient=peer, content='direct file')
        group_message = GroupMessage.objects.create(group=group, sender=uploader, content='group file')
        direct_attachment = MessageAttachment.objects.create(
            uploader=uploader,
            message=direct_message,
            file=SimpleUploadedFile('photo.png', b'image', content_type='image/png'),
            original_name='photo.png',
            attachment_type='image',
            mime_type='image/png',
            size=5,
        )
        group_attachment = MessageAttachment.objects.create(
            uploader=uploader,
            group_message=group_message,
            file=SimpleUploadedFile('brief.pdf', b'file', content_type='application/pdf'),
            original_name='brief.pdf',
            attachment_type='file',
            mime_type='application/pdf',
            size=4,
        )
        MessageAttachment.objects.create(
            uploader=other,
            file=SimpleUploadedFile('other.txt', b'other', content_type='text/plain'),
            original_name='other.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=5,
        )
        login(self.client, uploader)

        body = parse(self.client.get(reverse('list_my_message_attachments_api')))
        by_id = {item['id']: item for item in body['attachments']}
        self.assertEqual(set(by_id), {direct_attachment.id, group_attachment.id})
        self.assertEqual(by_id[direct_attachment.id]['context']['type'], 'direct')
        self.assertEqual(by_id[direct_attachment.id]['context']['peer_id'], peer.id)
        self.assertEqual(by_id[group_attachment.id]['context']['type'], 'group')
        self.assertEqual(by_id[group_attachment.id]['context']['group_id'], group.id)

        filtered = parse(self.client.get(f"{reverse('list_my_message_attachments_api')}?type=image"))
        self.assertEqual([item['id'] for item in filtered['attachments']], [direct_attachment.id])

    def test_accessible_message_attachments_respect_direct_and_group_visibility(self):
        owner = make_user('att_access_owner')
        member = make_user('att_access_member')
        group = self._create_group_directly(owner, [member])
        direct_message = Message.objects.create(sender=owner, recipient=member, content='direct')
        visible_group_message = GroupMessage.objects.create(group=group, sender=owner, content='visible')
        hidden_group_message = GroupMessage.objects.create(group=group, sender=owner, content='hidden')
        MessageGroupMember.objects.filter(group=group, user=member).update(
            joined_at=hidden_group_message.created_at + timedelta(seconds=1)
        )
        group.allow_new_members_view_history = False
        group.save(update_fields=['allow_new_members_view_history'])
        direct_attachment = MessageAttachment.objects.create(
            uploader=owner,
            message=direct_message,
            file=SimpleUploadedFile('shared-direct.txt', b'direct', content_type='text/plain'),
            original_name='shared-direct.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=6,
        )
        visible_attachment = MessageAttachment.objects.create(
            uploader=owner,
            group_message=visible_group_message,
            file=SimpleUploadedFile('shared-group.txt', b'group', content_type='text/plain'),
            original_name='shared-group.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=5,
        )
        hidden_attachment = MessageAttachment.objects.create(
            uploader=owner,
            group_message=hidden_group_message,
            file=SimpleUploadedFile('hidden-group.txt', b'hidden', content_type='text/plain'),
            original_name='hidden-group.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=6,
        )

        login(self.client, member)
        body = parse(self.client.get(f"{reverse('list_my_message_attachments_api')}?scope=accessible"))
        attachment_ids = {item['id'] for item in body['attachments']}
        self.assertEqual(body['scope'], 'accessible')
        self.assertIn(direct_attachment.id, attachment_ids)
        self.assertNotIn(hidden_attachment.id, attachment_ids)
        self.assertNotIn(visible_attachment.id, attachment_ids)

        membership = MessageGroupMember.objects.get(group=group, user=member)
        membership.joined_at = visible_group_message.created_at - timedelta(seconds=1)
        membership.save(update_fields=['joined_at'])
        refreshed = parse(self.client.get(f"{reverse('list_my_message_attachments_api')}?scope=accessible"))
        self.assertIn(visible_attachment.id, {item['id'] for item in refreshed['attachments']})

    def test_group_shared_items_lists_media_files_and_filters_hidden_messages(self):
        owner = make_user('grp_shared_owner')
        member = make_user('grp_shared_member')
        outsider = make_user('grp_shared_outsider')
        group = self._create_group_directly(owner, [member])
        visible_message = GroupMessage.objects.create(
            group=group,
            sender=owner,
            content='docs https://example.com/spec',
        )
        deleted_message = GroupMessage.objects.create(group=group, sender=owner, content='deleted')
        recalled_message = GroupMessage.objects.create(
            group=group,
            sender=owner,
            content='recalled',
            is_recalled=True,
        )
        deleted_message.deletions.create(user=member)

        MessageAttachment.objects.create(
            uploader=owner,
            group_message=visible_message,
            file=SimpleUploadedFile('preview.png', b'image-bytes', content_type='image/png'),
            original_name='preview.png',
            attachment_type='image',
            mime_type='image/png',
            size=11,
        )
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=visible_message,
            file=SimpleUploadedFile('brief.pdf', b'file-bytes', content_type='application/pdf'),
            original_name='brief.pdf',
            attachment_type='file',
            mime_type='application/pdf',
            size=10,
        )
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=deleted_message,
            file=SimpleUploadedFile('hidden.txt', b'hidden', content_type='text/plain'),
            original_name='hidden.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=6,
        )
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=recalled_message,
            file=SimpleUploadedFile('recalled.png', b'hidden', content_type='image/png'),
            original_name='recalled.png',
            attachment_type='image',
            mime_type='image/png',
            size=6,
        )

        login(self.client, member)
        response = self.client.get(reverse('group_shared_items_api', args=[group.id]))
        self.assertEqual(response.status_code, 200, response.content)
        body = parse(response)
        self.assertEqual([item['name'] for item in body['media']], ['preview.png'])
        self.assertEqual([item['name'] for item in body['files']], ['brief.pdf'])
        self.assertEqual(body['media'][0]['category'], 'media')
        self.assertEqual(body['files'][0]['category'], 'file')
        self.assertEqual(body['media'][0]['sender']['username'], owner.username)
        self.assertEqual(body['media'][0]['message_id'], visible_message.id)
        self.assertEqual(body['links'][0]['url'], 'https://example.com/spec')
        self.assertFalse(any(item['name'] == 'hidden.txt' for item in body['files']))
        self.assertFalse(any(item['name'] == 'recalled.png' for item in body['media']))

        self.client.logout()
        login(self.client, outsider)
        forbidden = self.client.get(reverse('group_shared_items_api', args=[group.id]))
        self.assertEqual(forbidden.status_code, 403, forbidden.content)

    def test_group_shared_items_cache_is_member_scoped(self):
        owner = make_user('grp_shared_cache_owner')
        member = make_user('grp_shared_cache_member')
        group = self._create_group_directly(owner, [member])
        visible_to_all = GroupMessage.objects.create(group=group, sender=owner, content='public link https://example.com/a')
        hidden_from_member = GroupMessage.objects.create(group=group, sender=owner, content='private link https://example.com/b')
        hidden_from_member.deletions.create(user=member)
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=visible_to_all,
            file=SimpleUploadedFile('all.txt', b'all', content_type='text/plain'),
            original_name='all.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=3,
        )
        MessageAttachment.objects.create(
            uploader=owner,
            group_message=hidden_from_member,
            file=SimpleUploadedFile('owner-only.txt', b'owner', content_type='text/plain'),
            original_name='owner-only.txt',
            attachment_type='file',
            mime_type='text/plain',
            size=5,
        )

        login(self.client, owner)
        owner_body = parse(self.client.get(reverse('group_shared_items_api', args=[group.id])))
        self.assertEqual({item['name'] for item in owner_body['files']}, {'all.txt', 'owner-only.txt'})

        self.client.logout()
        login(self.client, member)
        member_body = parse(self.client.get(reverse('group_shared_items_api', args=[group.id])))
        self.assertEqual({item['name'] for item in member_body['files']}, {'all.txt'})

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

    def test_group_mute_notice_is_only_visible_to_target_and_managers(self):
        owner = make_user('grp_notice_owner')
        muted_member = make_user('grp_notice_muted')
        observer = make_user('grp_notice_observer')
        group = self._create_group_directly(owner, [muted_member, observer])

        login(self.client, owner)
        response = post_json(self.client, reverse('mute_group_member_api', args=[group.id, muted_member.id]), {
            'duration_minutes': 60,
        })
        self.assertEqual(response.status_code, 200, response.content)
        notice_id = parse(response)['notice']['id']
        notice = GroupMessage.objects.get(pk=notice_id)
        self.assertEqual(notice.visibility_scope, GroupMessage.VISIBILITY_STAFF_AND_TARGET)
        self.assertEqual(notice.visibility_target_id, muted_member.id)

        owner_messages = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))['messages']
        self.assertIn(notice_id, [message['id'] for message in owner_messages])

        self.client.logout()
        login(self.client, muted_member)
        target_messages = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))['messages']
        self.assertIn(notice_id, [message['id'] for message in target_messages])

        self.client.logout()
        login(self.client, observer)
        observer_messages = parse(self.client.get(reverse('get_group_messages_api', args=[group.id])))['messages']
        self.assertNotIn(notice_id, [message['id'] for message in observer_messages])
        conversations = parse(self.client.get(reverse('get_message_conversations_api')))['conversations']
        observer_group = next(item for item in conversations if item.get('group_id') == group.id)
        self.assertNotEqual(observer_group['last_message'], notice.content)

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

        duplicate_response = post_json(self.client, reverse('group_invite_links_api', args=[group.id]), {})
        self.assertEqual(duplicate_response.status_code, 409, duplicate_response.content)
        self.assertEqual(MessageGroupInviteLink.objects.filter(group=group).count(), 1)

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

    def test_approval_invite_consumes_one_use_for_new_pending_request(self):
        owner = make_user('grp_invite_approval_owner')
        applicant = make_user('grp_invite_approval_applicant')
        second = make_user('grp_invite_approval_second')
        group = self._create_group_directly(owner, [])
        group.require_approval = True
        group.save(update_fields=['require_approval'])
        invite = MessageGroupInviteLink.objects.create(group=group, created_by=owner, max_uses=1)

        login(self.client, applicant)
        response = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(response.status_code, 202, response.content)
        invite.refresh_from_db()
        self.assertEqual(invite.uses_count, 1)
        self.assertEqual(MessageGroupInviteUse.objects.filter(invite=invite, user=applicant).count(), 1)
        join_request = GroupJoinRequest.objects.get(group=group, user=applicant, status='pending')
        self.assertEqual(join_request.source_invite, invite)
        self.assertIsNotNone(join_request.source_invite_use)
        self.assertEqual(join_request.source_invite_use.user, applicant)

        repeat = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {'request_message': 'again'})
        self.assertEqual(repeat.status_code, 400, repeat.content)
        invite.refresh_from_db()
        self.assertEqual(invite.uses_count, 1)

        self.client.logout()
        login(self.client, second)
        blocked = post_json(self.client, reverse('join_group_by_invite_api', args=[invite.token]), {})
        self.assertEqual(blocked.status_code, 400, blocked.content)
        self.assertFalse(GroupJoinRequest.objects.filter(group=group, user=second).exists())

    def test_group_join_request_can_be_approved_after_previous_approval_history(self):
        owner = make_user('grp_rejoin_owner')
        applicant = make_user('grp_rejoin_applicant')
        group = self._create_group_directly(owner, [])
        group.require_approval = True
        group.save(update_fields=['require_approval'])

        GroupJoinRequest.objects.create(
            group=group,
            user=applicant,
            status='approved',
            reviewed_by=owner,
            reviewed_at=timezone.now(),
        )
        MessageGroupMember.objects.create(
            group=group,
            user=applicant,
            role='member',
            left_at=timezone.now(),
        )
        pending_request = GroupJoinRequest.objects.create(
            group=group,
            user=applicant,
            status='pending',
        )

        login(self.client, owner)
        response = post_json(
            self.client,
            reverse('review_join_request_api', args=[group.id, pending_request.id]),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 200, response.content)
        pending_request.refresh_from_db()
        self.assertEqual(pending_request.status, 'approved')
        self.assertEqual(
            GroupJoinRequest.objects.filter(group=group, user=applicant, status='approved').count(),
            2,
        )
        self.assertTrue(
            MessageGroupMember.objects.filter(group=group, user=applicant, left_at__isnull=True).exists()
        )
        membership = MessageGroupMember.objects.get(group=group, user=applicant)
        self.assertIsNotNone(membership.cleared_before)

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
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(parse(response)['code'], 'require_2fa_setup')
        group.refresh_from_db()
        self.assertTrue(group.is_active)

        self._enable_2fa(owner)
        response = post_json(self.client, reverse('dissolve_message_group_api', args=[group.id]), {})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(parse(response)['code'], 'require_2fa')

        with patch('accounts.services.verify_2fa_for_request', return_value=(True, '')):
            response = post_json(self.client, reverse('dissolve_message_group_api', args=[group.id]), {
                'two_fa_code': '123456',
            })
        self.assertEqual(response.status_code, 200, response.content)
        group.refresh_from_db()
        self.assertFalse(group.is_active)

    def test_readding_left_member_sets_cleared_before(self):
        owner = make_user('grp_readd_owner')
        member = make_user('grp_readd_member')
        group = self._create_group_directly(owner, [member])
        membership = MessageGroupMember.objects.get(group=group, user=member)
        membership.left_at = timezone.now()
        membership.cleared_before = None
        membership.save(update_fields=['left_at', 'cleared_before'])

        login(self.client, owner)
        response = post_json(self.client, reverse('add_group_members_api', args=[group.id]), {
            'member_ids': [member.id],
        })

        self.assertEqual(response.status_code, 200, response.content)
        membership.refresh_from_db()
        self.assertIsNone(membership.left_at)
        self.assertIsNotNone(membership.cleared_before)

    def test_group_profile_transfer_mute_mode_and_audit_logs(self):
        owner = make_user('grp_ext_owner')
        member = make_user('grp_ext_member')
        admin_user = make_user('grp_ext_admin')
        group = self._create_group_directly(owner, [member, admin_user])
        MessageGroupPolicy.objects.create(min_public_notes=10, min_followers=2)
        for i in range(10):
            Note.objects.create(author=member, title=f'public note {i}', content='', is_public=True)
        for i in range(2):
            follower = make_user(f'grp_ext_follower_{i}')
            UserFollow.objects.create(follower=follower, following=member)
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

    def test_group_member_visibility_hides_member_list_from_regular_members(self):
        owner = make_user('grp_vis_owner')
        member = make_user('grp_vis_member')
        other = make_user('grp_vis_other')
        group = self._create_group_directly(owner, [member, other])

        login(self.client, owner)
        response = post_json(self.client, reverse('update_group_profile_api', args=[group.id]), {
            'members_visible': False,
        })
        self.assertEqual(response.status_code, 200, response.content)
        owner_body = parse(response)['group']
        self.assertFalse(owner_body['members_visible'])
        self.assertTrue(owner_body['can_view_members'])
        self.assertEqual(len(owner_body['members']), 3)

        self.client.logout()
        login(self.client, member)
        detail_response = self.client.get(reverse('message_group_detail_api', args=[group.id]))
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        member_body = parse(detail_response)['group']
        self.assertFalse(member_body['members_visible'])
        self.assertFalse(member_body['can_view_members'])
        self.assertEqual(member_body['member_count'], 3)
        self.assertEqual(member_body['members'], [])

    def test_hidden_group_members_block_active_mentions_but_allow_quoted_sender(self):
        owner = make_user('grp_mention_owner')
        member = make_user('grp_mention_member')
        other = make_user('grp_mention_other')
        group = self._create_group_directly(owner, [member, other])
        group.members_visible = False
        group.allow_member_mention_all = True
        group.save(update_fields=['members_visible', 'allow_member_mention_all'])

        owner_message = GroupMessage.objects.create(group=group, sender=owner, content='owner message')

        login(self.client, member)
        blocked_response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': f'hello @{other.username}',
            'mentions': [other.username],
        })
        self.assertEqual(blocked_response.status_code, 403, blocked_response.content)
        self.assertIn('不能主动', parse(blocked_response)['error'])

        mention_all_response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': '@全体成员 ping',
            'mention_all': True,
        })
        self.assertEqual(mention_all_response.status_code, 403, mention_all_response.content)

        quoted_response = post_json(self.client, reverse('send_group_message_api', args=[group.id]), {
            'content': f'> 引用 @{owner.username}: owner message\n\n收到',
            'reply_to': owner_message.id,
            'mentions': [owner.username],
        })
        self.assertEqual(quoted_response.status_code, 201, quoted_response.content)
        message_id = parse(quoted_response)['message']['id']
        self.assertTrue(
            GroupMessageMention.objects.filter(message_id=message_id, mentioned_user=owner).exists()
        )
        self.assertTrue(
            UserNotification.objects.filter(user=owner, kind='group_mention', data__message_id=message_id).exists()
        )

    def test_group_announcement_read_receipts(self):
        owner = make_user('grp_ann_owner')
        member = make_user('grp_ann_member')
        group = self._create_group_directly(owner, [member])
        login(self.client, owner)

        update_response = post_json(self.client, reverse('update_group_announcement_api', args=[group.id]), {
            'announcement': 'read this',
            'pin': True,
        })
        self.assertEqual(update_response.status_code, 200, update_response.content)
        body = parse(update_response)
        self.assertEqual(body['read_stats']['read_count'], 1)
        self.assertEqual(body['read_stats']['total_members'], 2)
        self.assertTrue(MessageGroupAnnouncementRead.objects.filter(group=group, user=owner).exists())

        self.client.logout()
        login(self.client, member)
        status_response = self.client.get(reverse('group_announcement_reads_api', args=[group.id]))
        self.assertEqual(status_response.status_code, 200, status_response.content)
        member_stats = parse(status_response)['read_stats']
        self.assertEqual(member_stats['read_count'], 1)
        self.assertFalse(member_stats['viewer_has_read'])
        self.assertEqual(member_stats['unread_users'], [])

        mark_response = post_json(self.client, reverse('group_announcement_reads_api', args=[group.id]), {})
        self.assertEqual(mark_response.status_code, 200, mark_response.content)
        self.assertEqual(parse(mark_response)['read_stats']['read_count'], 2)

        self.client.logout()
        login(self.client, owner)
        owner_response = self.client.get(reverse('group_announcement_reads_api', args=[group.id]))
        self.assertEqual(owner_response.status_code, 200, owner_response.content)
        owner_stats = parse(owner_response)['read_stats']
        self.assertTrue(owner_stats['viewer_has_read'])
        self.assertEqual(owner_stats['unread_users'], [])

    def test_edit_group_announcement_updates_linked_message_without_resending(self):
        owner = make_user('grp_ann_edit_owner')
        member = make_user('grp_ann_edit_member')
        group = self._create_group_directly(owner, [member])
        login(self.client, owner)

        create_response = post_json(self.client, reverse('update_group_announcement_api', args=[group.id]), {
            'announcement': 'first announcement',
            'pin': True,
        })
        self.assertEqual(create_response.status_code, 200, create_response.content)
        history = MessageGroupAnnouncementHistory.objects.get(group=group)
        message = history.message
        self.assertIsNotNone(message)
        self.assertEqual(GroupMessage.objects.filter(group=group).count(), 1)

        edit_response = post_json(
            self.client,
            reverse('group_announcement_detail_api', args=[group.id, history.id]),
            {
                'announcement': 'edited announcement',
                'pin': False,
            },
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.content)
        self.assertEqual(GroupMessage.objects.filter(group=group).count(), 1)
        message.refresh_from_db()
        history.refresh_from_db()
        self.assertIn('edited announcement', message.content)
        self.assertTrue(message.is_edited)
        self.assertEqual(history.content, 'edited announcement')
        self.assertFalse(history.pinned)

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
    def _create_group_directly(self, owner, members):
        group = MessageGroup.objects.create(
            name='forward attachment group',
            owner=owner,
            created_by=owner,
        )
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        for member in members:
            MessageGroupMember.objects.create(group=group, user=member, role='member')
        return group

    def test_forward_group_attachment_to_direct_message(self):
        owner = make_user('fwd_grp_file_owner')
        member = make_user('fwd_grp_file_member')
        recipient = make_user('fwd_grp_file_recipient')
        _enable_messaging(recipient)
        group = self._create_group_directly(owner, [member])
        source = GroupMessage.objects.create(group=group, sender=owner, content='')
        source_attachment = MessageAttachment.objects.create(
            uploader=owner,
            group_message=source,
            file=SimpleUploadedFile('meeting-notes.pdf', b'pdf bytes', content_type='application/pdf'),
            original_name='meeting-notes.pdf',
            attachment_type='file',
            mime_type='application/pdf',
            size=9,
        )

        login(self.client, member)
        response = post_json(self.client, reverse('forward_message_api'), {
            'group_message_id': source.id,
            'recipient_id': recipient.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        forwarded = Message.objects.get(sender=member, recipient=recipient)
        forwarded_attachment = forwarded.attachments.get()
        self.assertNotEqual(forwarded_attachment.id, source_attachment.id)
        self.assertEqual(forwarded_attachment.original_name, source_attachment.original_name)
        self.assertEqual(forwarded_attachment.attachment_type, source_attachment.attachment_type)
        self.assertEqual(forwarded_attachment.mime_type, source_attachment.mime_type)
        self.assertEqual(forwarded_attachment.size, source_attachment.size)
        self.assertEqual(forwarded_attachment.file.name, source_attachment.file.name)

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

    def test_get_messages_support_latest_page_pagination(self):
        alice = make_user('gm_page_a')
        bob = make_user('gm_page_b')
        for i in range(5):
            Message.objects.create(sender=alice, recipient=bob, content=f'private page {i}')

        login(self.client, alice)
        url = reverse('get_messages_api') + f'?user_id={bob.id}&limit=2'
        first_page = parse(self.client.get(url))
        self.assertEqual([m['content'] for m in first_page['messages']], ['private page 3', 'private page 4'])
        self.assertTrue(first_page['pagination']['has_more'])
        self.assertEqual(first_page['pagination']['next_offset'], 2)

        second_page = parse(self.client.get(url + '&offset=2'))
        self.assertEqual([m['content'] for m in second_page['messages']], ['private page 1', 'private page 2'])
        self.assertTrue(second_page['pagination']['has_more'])

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

    def test_group_listing_uses_visible_last_message_announcement_and_unread_count(self):
        owner = make_user('cv05_owner')
        member = make_user('cv05_member')
        login(self.client, member)

        group = MessageGroup.objects.create(name='team room', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        membership = MessageGroupMember.objects.create(group=group, user=member, role='member')

        now = timezone.now()
        membership.last_read_at = now - timedelta(hours=3)
        membership.cleared_before = now - timedelta(hours=2)
        membership.save(update_fields=['last_read_at', 'cleared_before'])

        old_message = GroupMessage.objects.create(group=group, sender=owner, content='old hidden by clear')
        visible_message = GroupMessage.objects.create(group=group, sender=owner, content='visible latest')
        deleted_message = GroupMessage.objects.create(group=group, sender=owner, content='deleted latest')

        GroupMessage.objects.filter(pk=old_message.pk).update(created_at=now - timedelta(hours=4))
        GroupMessage.objects.filter(pk=visible_message.pk).update(created_at=now - timedelta(minutes=30))
        GroupMessage.objects.filter(pk=deleted_message.pk).update(created_at=now - timedelta(minutes=5))
        deleted_message.deletions.create(user=member)

        MessageGroupAnnouncementHistory.objects.create(
            group=group,
            editor=owner,
            content='Heads up',
            pinned=True,
        )

        body = parse(self.client.get(reverse('get_message_conversations_api')))
        conversation = next(
            item for item in body['conversations']
            if item['conversation_type'] == 'group' and item['group_id'] == group.id
        )

        self.assertEqual(conversation['last_message'], 'visible latest')
        self.assertEqual(conversation['last_sender_id'], owner.id)
        self.assertEqual(conversation['announcement'], 'Heads up')
        self.assertTrue(conversation['announcement_pinned'])
        self.assertEqual(conversation['unread_count'], 1)


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
# direct-message mute
# =========================================================================
class DirectMessageMuteTests(_MessageTestBase):
    def test_set_mute_and_read_conversation_settings(self):
        owner = make_user('dmm01_owner')
        peer = make_user('dmm01_peer')
        login(self.client, owner)

        response = post_json(self.client, reverse('set_direct_message_mute_api'), {
            'user_id': peer.id,
            'duration_minutes': 60,
            'reason': 'Repeated unsolicited messages',
        })

        self.assertEqual(response.status_code, 200, response.content)
        mute = DirectMessageMute.objects.get(user=owner, muted_user=peer)
        self.assertTrue(mute.is_active)
        self.assertGreater(mute.expires_at, timezone.now())
        self.assertEqual(mute.reason, 'Repeated unsolicited messages')
        self.assertTrue(parse(response)['mute']['is_active'])

        settings_response = self.client.get(
            f"{reverse('get_conversation_settings_api')}?user_id={peer.id}"
        )
        self.assertEqual(settings_response.status_code, 200, settings_response.content)
        direct_mute = parse(settings_response)['settings']['direct_mute']
        self.assertTrue(direct_mute['is_active'])
        self.assertEqual(direct_mute['reason'], 'Repeated unsolicited messages')
        self.assertIsNotNone(direct_mute['expires_at'])

    def test_active_mute_prevents_peer_from_sending(self):
        owner = make_user('dmm02_owner')
        peer = make_user('dmm02_peer')
        _enable_messaging(owner)
        DirectMessageMute.objects.create(
            user=owner,
            muted_user=peer,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        login(self.client, peer)

        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': owner.id,
            'content': 'Please let me send this',
        })

        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Message.objects.filter(sender=peer, recipient=owner).exists())

    def test_expired_mute_does_not_block_peer(self):
        owner = make_user('dmm03_owner')
        peer = make_user('dmm03_peer')
        _enable_messaging(owner)
        DirectMessageMute.objects.create(
            user=owner,
            muted_user=peer,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        login(self.client, peer)

        response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': owner.id,
            'content': 'Allowed after expiry',
        })

        self.assertEqual(response.status_code, 201, response.content)

    def test_clear_mute_allows_peer_to_send_again(self):
        owner = make_user('dmm04_owner')
        peer = make_user('dmm04_peer')
        _enable_messaging(owner)
        DirectMessageMute.objects.create(user=owner, muted_user=peer)
        login(self.client, owner)

        clear_response = post_json(
            self.client,
            reverse('clear_direct_message_mute_api'),
            {'user_id': peer.id},
        )
        self.assertEqual(clear_response.status_code, 200, clear_response.content)
        self.assertFalse(DirectMessageMute.objects.filter(user=owner, muted_user=peer).exists())
        self.assertFalse(parse(clear_response)['mute']['is_active'])

        self.client.logout()
        login(self.client, peer)
        send_response = post_json(self.client, reverse('send_message_api'), {
            'recipient_id': owner.id,
            'content': 'Allowed after clearing',
        })
        self.assertEqual(send_response.status_code, 201, send_response.content)

    def test_rejects_self_mute_and_invalid_duration(self):
        user = make_user('dmm05')
        login(self.client, user)
        self_mute = post_json(self.client, reverse('set_direct_message_mute_api'), {
            'user_id': user.id,
            'duration_minutes': 60,
        })
        self.assertEqual(self_mute.status_code, 400)

        peer = make_user('dmm05_peer')
        invalid = post_json(self.client, reverse('set_direct_message_mute_api'), {
            'user_id': peer.id,
            'duration_minutes': 0,
        })
        self.assertEqual(invalid.status_code, 400)


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
class GroupWorkItemApiTests(_MessageTestBase):
    def _create_group(self, owner, members):
        group = MessageGroup.objects.create(name='work group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        for member in members:
            MessageGroupMember.objects.create(group=group, user=member, role='member')
        return group

    def test_manager_creates_poll_member_votes_and_manager_closes(self):
        owner = make_user('work_poll_owner')
        member = make_user('work_poll_member')
        group = self._create_group(owner, [member])
        login(self.client, owner)

        response = post_json(self.client, reverse('group_polls_api', args=[group.id]), {
            'question': 'Which day?',
            'options': ['Monday', 'Tuesday'],
            'allow_multiple': False,
        })
        body = parse(response)

        self.assertEqual(response.status_code, 201)
        poll_id = body['poll']['id']
        self.assertEqual(GroupPoll.objects.filter(id=poll_id).count(), 1)

        login(self.client, member)
        vote_response = post_json(
            self.client,
            reverse('vote_group_poll_api', args=[group.id, poll_id]),
            {'option_ids': [body['poll']['options'][1]['id']]},
        )
        vote_body = parse(vote_response)
        self.assertEqual(vote_response.status_code, 200)
        self.assertEqual(vote_body['poll']['total_votes'], 1)
        self.assertTrue(vote_body['poll']['options'][1]['selected'])

        login(self.client, owner)
        close_response = post_json(self.client, reverse('close_group_poll_api', args=[group.id, poll_id]), {})
        self.assertEqual(close_response.status_code, 200)
        self.assertFalse(parse(close_response)['poll']['is_open'])

    def test_member_cannot_create_group_work_items(self):
        owner = make_user('work_member_owner')
        member = make_user('work_member_user')
        group = self._create_group(owner, [member])
        login(self.client, member)

        poll_response = post_json(self.client, reverse('group_polls_api', args=[group.id]), {
            'question': 'No permission',
            'options': ['A', 'B'],
        })
        task_response = post_json(self.client, reverse('group_tasks_api', args=[group.id]), {
            'title': 'No permission',
        })

        self.assertEqual(poll_response.status_code, 403)
        self.assertEqual(task_response.status_code, 403)

    def test_task_can_be_completed_by_assignee_but_not_other_member(self):
        owner = make_user('work_task_owner')
        assignee = make_user('work_task_assignee')
        other = make_user('work_task_other')
        group = self._create_group(owner, [assignee, other])
        login(self.client, owner)
        response = post_json(self.client, reverse('group_tasks_api', args=[group.id]), {
            'title': 'Prepare release notes',
            'description': 'Draft and share the release notes',
            'assignee_id': assignee.id,
        })
        task_id = parse(response)['task']['id']
        self.assertTrue(GroupTask.objects.filter(id=task_id, assignee=assignee).exists())

        login(self.client, other)
        blocked = post_json(self.client, reverse('complete_group_task_api', args=[group.id, task_id]), {})
        self.assertEqual(blocked.status_code, 403)

        login(self.client, assignee)
        complete = post_json(self.client, reverse('complete_group_task_api', args=[group.id, task_id]), {})
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(parse(complete)['task']['status'], 'completed')


class MessagePreferenceTests(_MessageTestBase):
    def test_get_default_preference(self):
        user = make_user('mp01')
        login(self.client, user)
        body = parse(self.client.get(reverse('get_message_preference_api')))
        self.assertIn(body['preference']['message_mode'],
                      ['all', 'followers_only', 'following_only', 'disabled'])
        self.assertIn('notify_group_mentions_email', body['preference'])
        self.assertIn('email_mention_group_ids', body['preference'])
        self.assertIn('available_email_mention_groups', body['preference'])

    def test_get_preference_rejects_other_user_id(self):
        user = make_user('mp01_owner')
        other = make_user('mp01_other')
        login(self.client, user)

        response = self.client.get(
            reverse('get_message_preference_api'),
            {'user_id': other.id},
        )

        self.assertEqual(response.status_code, 403)

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

    def test_update_quiet_hours(self):
        user = make_user('mp02_quiet')
        login(self.client, user)
        response = post_json(self.client, reverse('update_message_preference_api'), {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:30',
            'quiet_hours_end': '07:15',
        })
        self.assertEqual(response.status_code, 200, response.content)
        pref = MessagePreference.objects.get(user=user)
        self.assertTrue(pref.quiet_hours_enabled)
        self.assertEqual(pref.quiet_hours_start.strftime('%H:%M'), '22:30')
        self.assertEqual(pref.quiet_hours_end.strftime('%H:%M'), '07:15')

        body = parse(self.client.get(reverse('get_message_preference_api')))
        self.assertEqual(body['preference']['quiet_hours_start'], '22:30')
        self.assertEqual(body['preference']['quiet_hours_end'], '07:15')

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

    def test_update_group_mention_email_groups(self):
        user = make_user('mp05')
        group = MessageGroup.objects.create(name='mention group', owner=user, created_by=user)
        MessageGroupMember.objects.create(group=group, user=user, role='owner')
        login(self.client, user)

        response = post_json(self.client, reverse('update_message_preference_api'), {
            'notify_group_mentions_email': True,
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 200, response.content)
        pref = MessagePreference.objects.get(user=user)
        self.assertTrue(pref.notify_group_mentions_email)
        self.assertEqual(list(pref.email_mention_groups.values_list('id', flat=True)), [group.id])

    def test_update_rejects_unavailable_group_mention_email_group(self):
        user = make_user('mp06')
        owner = make_user('mp06_owner')
        group = MessageGroup.objects.create(name='unrelated group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        login(self.client, user)

        response = post_json(self.client, reverse('update_message_preference_api'), {
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 400)

    def test_update_rejects_other_user_id(self):
        user = make_user('mp07')
        other = make_user('mp07_other')
        login(self.client, user)

        response = post_json(self.client, reverse('update_message_preference_api'), {
            'user_id': other.id,
            'show_read_status': False,
        })

        self.assertEqual(response.status_code, 403)

    def test_update_is_atomic_when_group_ids_invalid(self):
        user = make_user('mp08')
        owner = make_user('mp08_owner')
        group = MessageGroup.objects.create(name='atomic bad group', owner=owner, created_by=owner)
        MessageGroupMember.objects.create(group=group, user=owner, role='owner')
        login(self.client, user)

        pref, _ = MessagePreference.objects.get_or_create(user=user)
        original_show_read_status = pref.show_read_status
        original_notify_group_mentions_email = pref.notify_group_mentions_email

        response = post_json(self.client, reverse('update_message_preference_api'), {
            'show_read_status': not original_show_read_status,
            'notify_group_mentions_email': not original_notify_group_mentions_email,
            'email_mention_group_ids': [group.id],
        })

        self.assertEqual(response.status_code, 400)
        pref.refresh_from_db()
        self.assertEqual(pref.show_read_status, original_show_read_status)
        self.assertEqual(pref.notify_group_mentions_email, original_notify_group_mentions_email)


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
        with patch('core.utils.turnstile.verify_turnstile_token', return_value=True):
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

    @patch('messaging.views.attachment.check_rate_limit_atomic', return_value=(False, 20))
    def test_upload_rate_limit_returns_429_before_creating_attachment(self, _mocked_rate_limit):
        user = make_user('ua_rate_limited')
        login(self.client, user)
        upload = SimpleUploadedFile('limited.txt', b'content', content_type='text/plain')

        response = self.client.post(reverse('upload_message_attachment_api'), {'file': upload})

        self.assertEqual(response.status_code, 429)
        self.assertFalse(MessageAttachment.objects.filter(uploader=user).exists())

    def test_upload_unsupported_type_returns_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = make_user('ua02')
        login(self.client, user)
        # text/html 不在白名单
        bad = SimpleUploadedFile('evil.html', b'<html></html>', content_type='text/html')
        response = self.client.post(reverse('upload_message_attachment_api'), {'file': bad})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MessageAttachment.objects.filter(uploader=user).exists())

    @override_settings(USER_STORAGE_QUOTA_BYTES=8)
    def test_upload_storage_quota_exceeded_returns_413(self):
        user = make_user('ua03_quota')
        login(self.client, user)
        upload = SimpleUploadedFile('quota.txt', b'0123456789', content_type='text/plain')

        response = self.client.post(reverse('upload_message_attachment_api'), {'file': upload})
        body = parse(response)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(body['code'], 'storage_quota_exceeded')
        self.assertFalse(MessageAttachment.objects.filter(uploader=user).exists())
