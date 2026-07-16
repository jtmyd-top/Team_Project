"""实时通知推送测试

覆盖:
- notify_user 在事务提交后向用户 WebSocket 组推送 notification 事件
- 事件负载包含序列化通知与未读数
- ChatConsumer.notification 处理器向客户端转发 JSON
- base.html 为登录用户注入 window.APP_REALTIME 配置
"""

from __future__ import annotations

import json
from unittest import mock

from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django.urls import reverse

from messaging.consumers import ChatConsumer
from notifications.models import UserNotification
from notifications.services import notify_user

from ._helpers import login, make_user


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class RealtimeNotificationTests(TestCase):
    def test_notify_user_pushes_realtime_event(self):
        user = make_user('rt01')
        with mock.patch('notifications.services.push_user_event') as push, \
                self.captureOnCommitCallbacks(execute=True):
            notification = notify_user(
                user, 'new_comment', '新评论', '有人评论了你的笔记', note_id=12,
            )

        self.assertIsNotNone(notification)
        push.assert_called_once()
        user_id, event = push.call_args.args
        self.assertEqual(user_id, user.id)
        self.assertEqual(event['type'], 'notification')
        self.assertEqual(event['unread_count'], 1)
        payload = event['notification']
        self.assertEqual(payload['id'], notification.id)
        self.assertEqual(payload['kind'], 'new_comment')
        self.assertEqual(payload['title'], '新评论')
        self.assertEqual(payload['data'], {'note_id': 12})
        self.assertFalse(payload['is_read'])

    def test_unread_count_includes_existing_unread(self):
        user = make_user('rt02')
        UserNotification.objects.create(
            user=user, kind='new_follower', title='新粉丝',
        )
        with mock.patch('notifications.services.push_user_event') as push, \
                self.captureOnCommitCallbacks(execute=True):
            notify_user(user, 'new_comment', '新评论')

        self.assertEqual(push.call_args.args[1]['unread_count'], 2)

    def test_notify_user_none_user_skips_push(self):
        with mock.patch('notifications.services.push_user_event') as push, \
                self.captureOnCommitCallbacks(execute=True):
            result = notify_user(None, 'new_comment', '新评论')

        self.assertIsNone(result)
        push.assert_not_called()

    def test_realtime_push_survives_deleted_notification(self):
        user = make_user('rt03')
        with mock.patch('notifications.services.push_user_event') as push:
            with self.captureOnCommitCallbacks() as callbacks:
                notification = notify_user(user, 'new_comment', '新评论')
            UserNotification.objects.filter(id=notification.id).delete()
            for callback in callbacks:
                callback()

        push.assert_not_called()

    def test_consumer_forwards_notification_event(self):
        consumer = ChatConsumer()
        sent = []

        async def capture(text_data=None, bytes_data=None, close=False):
            sent.append(text_data)

        consumer.send = capture
        async_to_sync(consumer.notification)({
            'type': 'notification',
            'notification': {'id': 5, 'kind': 'new_comment', 'title': '新评论'},
            'unread_count': 3,
        })

        self.assertEqual(len(sent), 1)
        payload = json.loads(sent[0])
        self.assertEqual(payload['type'], 'notification')
        self.assertEqual(payload['notification']['id'], 5)
        self.assertEqual(payload['unread_count'], 3)

    def test_base_template_injects_realtime_config(self):
        user = make_user('rt04')
        login(self.client, user)
        response = self.client.get(reverse('insights'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'APP_REALTIME')
        self.assertContains(response, 'realtime-notify.js')
