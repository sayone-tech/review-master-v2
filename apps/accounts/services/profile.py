from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User


@transaction.atomic
def update_profile_name(*, user: User, full_name: str) -> User:
    """Update the user's full_name. Trims whitespace."""
    user.full_name = full_name.strip()
    user.save(update_fields=["full_name", "updated_at"])
    return user


@transaction.atomic
def change_password(*, user: User, current_password: str, new_password: str) -> User:
    """Change password after verifying the current password.

    Raises ValueError with message 'Current password is incorrect.' when
    current_password fails check_password(). Caller is responsible for
    calling update_session_auth_hash() after this returns.
    """
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    return user
