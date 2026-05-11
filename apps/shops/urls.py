from __future__ import annotations

from django.urls import path

from apps.shops.views import GoogleOAuthCallbackView, GoogleOAuthStartView, shop_targets_view

urlpatterns = [
    path("oauth/google/start/", GoogleOAuthStartView.as_view(), name="oauth_google_start"),
    path("oauth/google/callback/", GoogleOAuthCallbackView.as_view(), name="oauth_google_callback"),
    path(
        "admin/org/shops/<int:shop_id>/targets/",
        shop_targets_view,
        name="shop_targets",
    ),
]
