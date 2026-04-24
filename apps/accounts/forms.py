from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise


class CustomAuthenticationForm(AuthenticationForm):
    """Authentication form with a generic error message (no email enumeration)."""

    error_messages: ClassVar[dict[str, str | StrPromise]] = {  # type: ignore[misc]
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }


class ActivationForm(forms.Form):
    """Org Admin account activation form (ACTV-02).

    Fields:
    - full_name: 2-100 chars (CharField with min/max validators)
    - password1: password, validated through Django AUTH_PASSWORD_VALIDATORS
    - password2: confirm password, must match password1

    This form does NOT include email — the view pre-fills a disabled email input
    from invitation.organisation.email; email is never accepted from POST (trust
    boundary).
    """

    full_name = forms.CharField(
        min_length=2,
        max_length=100,
        error_messages={
            "min_length": "Name must be at least 2 characters.",
            "max_length": "Name must be at most 100 characters.",
            "required": "Name is required.",
        },
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Password is required."},
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Please confirm your password."},
    )

    def clean_password1(self) -> str:
        pw: str = self.cleaned_data["password1"]
        try:
            validate_password(pw)
        except ValidationError as exc:
            raise forms.ValidationError(list(exc.messages)) from exc
        return pw

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned


class ProfileNameForm(forms.Form):
    """PROF-01 — name update form."""

    full_name = forms.CharField(
        min_length=2,
        max_length=100,
        strip=True,
        error_messages={
            "min_length": "Name must be at least 2 characters.",
            "max_length": "Name must be at most 100 characters.",
            "required": "Name is required.",
        },
    )


class ProfilePasswordChangeForm(forms.Form):
    """PROF-02 — password change form.

    NOTE: Do NOT use Django's built-in PasswordChangeForm — it requires the
    user at construction time and uses different field names. This custom
    form mirrors ActivationForm's pattern for consistency.
    """

    current_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Current password is required."},
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "New password is required."},
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Please confirm your new password."},
    )

    def clean_new_password(self) -> str:
        pw: str = self.cleaned_data["new_password"]
        try:
            validate_password(pw)
        except ValidationError as exc:
            raise forms.ValidationError(list(exc.messages)) from exc
        return pw

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned
