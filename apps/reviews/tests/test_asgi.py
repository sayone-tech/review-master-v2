"""INFRA-08: ASGI configured with ProtocolTypeRouter; CHANNEL_LAYERS set correctly."""

from channels.routing import ProtocolTypeRouter
from django.conf import settings

from config.asgi import application
from config.routing import websocket_urlpatterns


def test_application_is_protocol_router() -> None:
    assert isinstance(application, ProtocolTypeRouter)
    assert "http" in application.application_mapping
    assert "websocket" in application.application_mapping


def test_websocket_routing_includes_sync_progress() -> None:
    # The url pattern is registered.
    patterns = [str(p.pattern) for p in websocket_urlpatterns]
    assert any("ws/sync-progress" in p for p in patterns)


def test_in_memory_channel_layer_in_tests() -> None:
    assert settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer"


def test_asgi_application_setting() -> None:
    assert settings.ASGI_APPLICATION == "config.asgi.application"
