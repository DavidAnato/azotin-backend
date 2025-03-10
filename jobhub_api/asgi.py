"""
ASGI config for jobhub_api project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from app_messaging.middleware import JWTAuthMiddleware
from app_messaging.routing import (
    websocket_urlpatterns as messaging_websocket_urlpatterns,
)
from app_notification.routing import (
    websocket_urlpatterns as notification_websocket_urlpatterns,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobhub_api.settings.development")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": JWTAuthMiddleware(
            AuthMiddlewareStack(
                URLRouter(
                    messaging_websocket_urlpatterns + notification_websocket_urlpatterns
                )
            )
        ),
    }
)
