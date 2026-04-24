from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User


@transaction.atomic
def update_profile_name(*, user: User, full_name: str) -> User:
    """Update the user's full_name. Trims whitespace. Plan 05-02 implements."""
    raise NotImplementedError("Plan 05-02 implements update_profile_name")


@transaction.atomic
def change_password(*, user: User, current_password: str, new_password: str) -> User:
    """Change password after verifying current_password. Raises ValueError if wrong.
    Plan 05-03 implements.
    """
    raise NotImplementedError("Plan 05-03 implements change_password")
