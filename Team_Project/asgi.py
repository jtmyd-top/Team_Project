"""
ASGI config for Team_Project project.
"""

import os

from django.core.asgi import get_asgi_application
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')

django_asgi_app = get_asgi_application()

try:
    if getattr(settings, 'REALTIME_MESSAGES_ENABLED', False):
        from channels.auth import AuthMiddlewareStack
        from channels.routing import ProtocolTypeRouter, URLRouter
        from messaging.routing import websocket_urlpatterns

        application = ProtocolTypeRouter({
            'http': django_asgi_app,
            'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        })
    else:
        application = django_asgi_app
except ImportError:
    application = django_asgi_app
