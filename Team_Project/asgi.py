"""
ASGI config for Team_Project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')

django_asgi_app = get_asgi_application()

try:
    if getattr(settings, 'REALTIME_MESSAGES_ENABLED', False):
        from channels.auth import AuthMiddlewareStack
        from channels.routing import ProtocolTypeRouter, URLRouter
        from knowledge_project.routing import websocket_urlpatterns

        application = ProtocolTypeRouter({
            'http': django_asgi_app,
            'websocket': AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
        })
    else:
        application = django_asgi_app
except ImportError:
    application = django_asgi_app
