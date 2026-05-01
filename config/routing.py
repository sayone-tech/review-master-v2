"""WebSocket URL routing.

See CLAUDE.md §13.2: scope is intentionally narrow — only SyncProgressConsumer
in Phase 10. Adding new consumers requires updating CLAUDE.md §13 and code review.
"""

from django.urls import path

from apps.reviews.consumers import SyncProgressConsumer

websocket_urlpatterns = [
    path("ws/sync-progress/<int:shop_id>/", SyncProgressConsumer.as_asgi()),
]
