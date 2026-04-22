import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_role_enum_has_exactly_three_members() -> None:
    assert set(User.Role.values) == {"SUPERADMIN", "ORG_ADMIN", "STAFF_ADMIN"}


def test_create_user_normalises_email_and_sets_password() -> None:
    u = User.objects.create_user(
        email="A@Example.COM", password="secret12345", role="SUPERADMIN", full_name="Alice"
    )
    assert u.email == "A@example.com"  # domain lowercased per BaseUserManager.normalize_email
    assert u.check_password("secret12345") is True
    assert u.role == "SUPERADMIN"
    assert u.is_staff is False


def test_create_superuser_sets_staff_and_superuser_and_role() -> None:
    u = User.objects.create_superuser(
        email="boss@example.com", password="s3cret12345", full_name="Boss"
    )
    assert u.is_staff is True
    assert u.is_superuser is True
    assert u.role == "SUPERADMIN"


def test_duplicate_email_raises_integrity_error() -> None:
    User.objects.create_user(email="dup@example.com", password="testpass1234", role="ORG_ADMIN")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="testpass1234", role="ORG_ADMIN")


def test_user_inherits_timestamped_model() -> None:
    u = UserFactory()
    assert u.created_at is not None
    assert u.updated_at is not None


def test_str_returns_email() -> None:
    u = UserFactory(email="x@y.com")
    assert str(u) == "x@y.com"
