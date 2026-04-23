from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.http import HttpRequest, HttpResponse
from django.urls import reverse_lazy

from apps.accounts.forms import CustomAuthenticationForm
from apps.accounts.throttling import LoginRateThrottle

SESSION_AGE_24H = 60 * 60 * 24
SESSION_AGE_30D = 60 * 60 * 24 * 30
RATE_LIMIT_MESSAGE = "Too many sign-in attempts. Please try again in 15 minutes."


class CustomLoginView(LoginView):
    """Rate-limited LoginView with remember-me session expiry.

    - POST throttled by LoginRateThrottle (10/15min per IP, Redis DB 1)
    - GET never throttled (override post() only)
    - remember_me checkbox: checked → 30d session; unchecked → 24h session
    - redirect_authenticated_user = True: already-logged-in users land on LOGIN_REDIRECT_URL
    """

    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        throttle = LoginRateThrottle()
        if not throttle.allow_request(request, self):  # type: ignore[arg-type]
            return HttpResponse(
                RATE_LIMIT_MESSAGE, status=429, content_type="text/plain; charset=utf-8"
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: CustomAuthenticationForm) -> HttpResponse:  # type: ignore[override]
        remember = self.request.POST.get("remember_me")
        response = super().form_valid(form)
        if remember:
            self.request.session.set_expiry(SESSION_AGE_30D)
        else:
            self.request.session.set_expiry(SESSION_AGE_24H)
        return response


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Password-reset confirm view that redirects to /login/ with a flash."""

    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form: Any) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Password updated. Please sign in.",
        )
        return response
