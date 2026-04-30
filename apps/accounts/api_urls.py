from __future__ import annotations

from rest_framework.routers import SimpleRouter

from apps.accounts.views import TeamViewSet

router = SimpleRouter()
router.register(r"team", TeamViewSet, basename="team")

urlpatterns = router.urls
