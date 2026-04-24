from __future__ import annotations

import pytest

from apps.accounts.services.profile import change_password, update_profile_name
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestUpdateProfileName:
    def test_update_profile_name_saves_trimmed_value(self) -> None:
        user = UserFactory(full_name="Old Name")
        update_profile_name(user=user, full_name="  Alice  ")
        user.refresh_from_db()
        assert user.full_name == "Alice"

    def test_update_profile_name_returns_user(self) -> None:
        user = UserFactory()
        result = update_profile_name(user=user, full_name="Bob")
        assert result.pk == user.pk

    def test_update_profile_name_updates_timestamp(self) -> None:
        user = UserFactory()
        original_updated = user.updated_at
        update_profile_name(user=user, full_name="Carol")
        user.refresh_from_db()
        assert user.updated_at > original_updated


class TestChangePassword:
    def test_change_password_succeeds_with_correct_current(self) -> None:
        user = UserFactory(password="testpass1234")
        change_password(
            user=user,
            current_password="testpass1234",
            new_password="NewStrongPass!2026",
        )
        assert user.check_password("NewStrongPass!2026")

    def test_change_password_raises_on_wrong_current(self) -> None:
        user = UserFactory(password="testpass1234")
        with pytest.raises(ValueError, match="incorrect"):
            change_password(
                user=user,
                current_password="wrong-current",
                new_password="NewStrongPass!2026",
            )

    def test_change_password_persists_to_db(self) -> None:
        user = UserFactory(password="testpass1234")
        change_password(
            user=user,
            current_password="testpass1234",
            new_password="NewStrongPass!2026",
        )
        user.refresh_from_db()
        assert user.check_password("NewStrongPass!2026")
