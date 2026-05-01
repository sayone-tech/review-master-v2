"""ASGI application for Django + Channels.

See CLAUDE.md §13 and RESEARCH.md Pitfall 1 for import-order rules:
`get_asgi_application()` MUST be called BEFORE importing routing modules,
because routing imports consumer modules that may load Django models.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

# MUST be imported AFTER get_asgi_application() — RESEARCH.md Pitfall 1
from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
