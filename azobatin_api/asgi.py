"""
ASGI config for azobatin_api project.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "azobatin_api.settings.development")

import django  # noqa: E402

django.setup()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

from app_messaging.middleware import JWTAuthMiddleware  # noqa: E402
from app_messaging.routing import (  # noqa: E402
    websocket_urlpatterns as messaging_websocket_urlpatterns,
)
from app_notification.routing import (  # noqa: E402
    websocket_urlpatterns as notification_websocket_urlpatterns,
)

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
