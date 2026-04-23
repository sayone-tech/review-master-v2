from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.contrib.auth.forms import AuthenticationForm

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise


class CustomAuthenticationForm(AuthenticationForm):
    """Authentication form with a generic error message (no email enumeration)."""

    error_messages: ClassVar[dict[str, str | StrPromise]] = {  # type: ignore[misc]
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }
