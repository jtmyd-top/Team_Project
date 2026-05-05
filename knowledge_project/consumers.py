import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """私信实时通道。每个用户加入自己的广播组，接收多端同步事件。"""

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f'chat_user_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("私信 WebSocket 已连接: user=%s", self.user.id)

    async def disconnect(self, close_code):
        user_id = getattr(getattr(self, 'user', None), 'id', None)
        group_name = getattr(self, 'group_name', None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)
        logger.info("私信 WebSocket 已断开: user=%s, code=%s", user_id, close_code)

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

    async def handle_typing(self, payload):
        peer_id = payload.get('peer_id')
        try:
            peer_id = int(peer_id)
        except (TypeError, ValueError):
            return
        if peer_id <= 0 or peer_id == self.user.id:
            return
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

    @database_sync_to_async
    def has_conversation_with(self, peer_id):
        from .models import Message

        return Message.objects.filter(
            sender_id__in=[self.user.id, peer_id],
            recipient_id__in=[self.user.id, peer_id],
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
