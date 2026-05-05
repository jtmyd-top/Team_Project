import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def realtime_messages_enabled():
    return bool(getattr(settings, 'REALTIME_MESSAGES_ENABLED', False))


def push_user_event(user_id, event):
    """向指定用户组推送事件。未启用实时层时静默返回。"""
    if not realtime_messages_enabled():
        return False

    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        logger.debug("Channels 未安装，跳过实时推送")
        return False

    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(f'chat_user_{user_id}', event)
        return True
    except Exception as exc:
        logger.warning(
            "实时推送失败: user=%s, event=%s, error=%s",
            user_id,
            event.get('type'),
            exc,
            exc_info=True,
        )
        return False
