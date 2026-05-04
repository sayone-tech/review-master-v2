"""Phase 13 plan 04 — ActionItem API router + template page URL."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.action_items.views import ActionItemViewSet, action_item_list_view

router = DefaultRouter()
router.register(r"action-items", ActionItemViewSet, basename="action-item")

api_urlpatterns = router.urls

urlpatterns = [
    path("admin/org/action-items/", action_item_list_view, name="action_item_list"),
]
