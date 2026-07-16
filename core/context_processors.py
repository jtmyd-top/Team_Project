from django.conf import settings


def realtime(request):
    """把实时推送配置暴露给所有模板（base.html 注入 window.APP_REALTIME）。"""
    return {
        'realtime_enabled': bool(getattr(settings, 'REALTIME_MESSAGES_ENABLED', False)),
        'realtime_ws_path': getattr(settings, 'REALTIME_MESSAGES_PATH', '/ws/messages/'),
    }
