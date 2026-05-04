"""Phase 13 plan 05 — Notification API router.

13-05 owns this file outright (B2-residual fix). 13-04 deliberately did NOT
create or touch it because Django's include("module.path") resolves eagerly
at URL config build time, which would have broken `manage.py check` before
13-05 landed. With this module in place, config/urls.py wires it under
api/v1/ in the same plan.
"""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.notifications.views import NotificationViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")

api_urlpatterns = router.urls
