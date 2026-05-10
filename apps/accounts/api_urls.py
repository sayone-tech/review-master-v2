from __future__ import annotations

from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import MobileTokenObtainPairView
from apps.accounts.views import TeamViewSet

router = SimpleRouter()
router.register(r"team", TeamViewSet, basename="team")

urlpatterns = [
    *router.urls,
    path("auth/token/", MobileTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
