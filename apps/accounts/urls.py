from __future__ import annotations

from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import CustomLoginView, CustomPasswordResetConfirmView

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/login/"),
        name="logout",
    ),
    # Password reset URL skeleton — Plan 03 customises templates + email + confirm view.
    # Registered here so {% url 'password_reset' %} resolves from the login template
    # AND the stub templates created above keep the reset URLs from raising
    # TemplateDoesNotExist before Plan 03 fills them in.
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="emails/password_reset.txt",
            html_email_template_name="emails/password_reset.html",
            subject_template_name="emails/password_reset_subject.txt",
            success_url="/password-reset/done/",
            extra_email_context={"site_name": "Review Master"},
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
