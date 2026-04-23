from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from apps.accounts.forms import ActivationForm, CustomAuthenticationForm
from apps.accounts.models import InvitationToken
from apps.accounts.throttling import LoginRateThrottle

SESSION_AGE_24H = 60 * 60 * 24
SESSION_AGE_30D = 60 * 60 * 24 * 30
RATE_LIMIT_MESSAGE = "Too many sign-in attempts. Please try again in 15 minutes."


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/profile.html")


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


ACTV04_COPY = (
    "This invitation link is invalid or has expired. "
    "Please contact your administrator to request a new one."
)
ACTV05_COPY = "This invitation has already been used."


def invite_accept_view(request: HttpRequest, token: str) -> HttpResponse:
    """Public (no @login_required) — ACTV-01..05.

    Three token states (checked in this exact order):
    1. Not found or tamper: render invite_error with ACTV-04 copy
    2. is_used: render invite_error with ACTV-05 copy (CHECKED BEFORE expired)
    3. is_expired: render invite_error with ACTV-04 copy
    4. Valid: render activation form (GET) or process it (POST)

    On POST success: activate_account(), login(user), redirect org_admin_dashboard.
    """
    token_hash = InvitationToken.hash_token(token)
    try:
        invitation = InvitationToken.objects.select_related("organisation").get(
            token_hash=token_hash
        )
    except InvitationToken.DoesNotExist:
        return render(request, "accounts/invite_error.html", {"message": ACTV04_COPY})

    # CRITICAL ORDER: is_used FIRST, then is_expired. A resend makes the old token
    # is_used=True while leaving expires_at untouched — we want ACTV-05 copy in that case.
    if invitation.is_used:
        return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
    if invitation.is_expired:
        return render(request, "accounts/invite_error.html", {"message": ACTV04_COPY})

    organisation = invitation.organisation

    if request.method == "POST":
        form = ActivationForm(request.POST)
        if form.is_valid():
            from apps.organisations.services.organisations import activate_account

            try:
                user = activate_account(
                    invitation=invitation,
                    full_name=form.cleaned_data["full_name"],
                    password=form.cleaned_data["password1"],
                )
            except ValidationError:
                # Race: someone else activated between is_used check and now.
                return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
            login(request, user)
            return redirect(reverse("org_admin_dashboard"))
    else:
        form = ActivationForm()

    return render(
        request,
        "accounts/invite_accept.html",
        {
            "form": form,
            "organisation": organisation,
            "email": organisation.email,
        },
    )
