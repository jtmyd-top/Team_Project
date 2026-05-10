import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# 服务端 typing 事件限流：每个用户每个对话最短间隔（秒）
_TYPING_RATE_LIMIT_SECONDS = 1.0


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
        # 记录每个对话最近一次转发 typing 事件的时间戳，用于服务端限流
        # key: peer_id (int), value: float (time.monotonic)
        self._typing_last_sent: dict[int, float] = {}
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

        # 服务端限流：同一对话的 typing 事件转发间隔不得小于 _TYPING_RATE_LIMIT_SECONDS
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
        """转发 typing_stop 事件，让对端立即清除"对方正在输入"指示。

        与 typing 不同，stop 事件不做服务端限流（量本身很小：每段输入最多触发
        一次），但仍校验 peer_id 与对话关系，且会重置该对话的 typing 节流时间戳，
        避免 stop 之后 1 秒内的下一次 typing 因为节流而丢失。
        """
        peer_id = payload.get('peer_id')
        try:
            peer_id = int(peer_id)
        except (TypeError, ValueError):
            return
        if peer_id <= 0 or peer_id == self.user.id:
            return

        # 重置该对话的节流时间戳，确保用户"清空 → 重新开始输入"时不会被限流吞掉
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

        from .models import Message

        # 使用 Q 对象精确匹配双向对话，避免 __in 笛卡尔积误匹配
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
