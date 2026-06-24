import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

_TYPING_RATE_LIMIT_SECONDS = 1.0


class ChatConsumer(AsyncWebsocketConsumer):
    """Private-message realtime channel."""

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f'chat_user_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        self._typing_last_sent = {}
        logger.info("Private message WebSocket connected: user=%s", self.user.id)

    async def disconnect(self, close_code):
        user_id = getattr(getattr(self, 'user', None), 'id', None)
        group_name = getattr(self, 'group_name', None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        logger.info("Private message WebSocket disconnected: user=%s, code=%s", user_id, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if payload.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        if payload.get('type') == 'typing':
            await self.handle_typing(payload)
            return

        if payload.get('type') == 'typing_stop':
            await self.handle_typing_stop(payload)

    async def handle_typing(self, payload):
        peer_id = payload.get('peer_id')
        try:
            peer_id = int(peer_id)
        except (TypeError, ValueError):
            return
        if peer_id <= 0 or peer_id == self.user.id:
            return

        now = time.monotonic()
        last_sent = self._typing_last_sent.get(peer_id, 0.0)
        if now - last_sent < _TYPING_RATE_LIMIT_SECONDS:
            return
        self._typing_last_sent[peer_id] = now

        if not await self.has_conversation_with(peer_id):
            return

        await self.channel_layer.group_send(
            f'chat_user_{peer_id}',
            {
                'type': 'typing',
                'peer_id': self.user.id,
                'username': self.user.username,
            },
        )

    async def handle_typing_stop(self, payload):
        peer_id = payload.get('peer_id')
        try:
            peer_id = int(peer_id)
        except (TypeError, ValueError):
            return
        if peer_id <= 0 or peer_id == self.user.id:
            return

        self._typing_last_sent.pop(peer_id, None)

        if not await self.has_conversation_with(peer_id):
            return

        await self.channel_layer.group_send(
            f'chat_user_{peer_id}',
            {
                'type': 'typing_stop',
                'peer_id': self.user.id,
            },
        )

    @database_sync_to_async
    def has_conversation_with(self, peer_id):
        from django.db.models import Q

        from messaging.models import Message

        return Message.objects.filter(
            Q(sender_id=self.user.id, recipient_id=peer_id)
            | Q(sender_id=peer_id, recipient_id=self.user.id)
        ).exists()

    async def new_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'peer_id': event['peer_id'],
        }))

    async def message_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_read',
            'message_ids': event['message_ids'],
            'reader_id': event['reader_id'],
            'peer_id': event['peer_id'],
        }))

    async def message_recalled(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_recalled',
            'message_id': event['message_id'],
            'peer_id': event['peer_id'],
        }))

    async def typing(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'peer_id': event['peer_id'],
            'username': event.get('username', ''),
        }))

    async def typing_stop(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing_stop',
            'peer_id': event['peer_id'],
        }))

    async def group_join_request(self, event):
        """处理群组加入申请通知"""
        await self.send(text_data=json.dumps({
            'type': 'group_join_request',
            'group_id': event['group_id'],
            'group_name': event.get('group_name', ''),
            'request_id': event.get('request_id'),
            'user': event.get('user', {}),
            'request_message': event.get('request_message', ''),
        }))
