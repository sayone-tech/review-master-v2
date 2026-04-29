from __future__ import annotations

from django.urls import path

from apps.shops.views import GoogleOAuthCallbackView, GoogleOAuthStartView

urlpatterns = [
    path("oauth/google/start/", GoogleOAuthStartView.as_view(), name="oauth_google_start"),
    path("oauth/google/callback/", GoogleOAuthCallbackView.as_view(), name="oauth_google_callback"),
]
