from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import InvitationToken, User
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory

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


# Task 3: User.organisation FK tests
def test_user_organisation_is_nullable() -> None:
    u = UserFactory(organisation=None)
    assert u.organisation is None


def test_user_organisation_fk_assigns_and_retrieves() -> None:
    org = OrganisationFactory()
    u = UserFactory(organisation=org)
    u.refresh_from_db()
    assert u.organisation_id == org.id


def test_deleting_organisation_nullifies_user_organisation() -> None:
    org = OrganisationFactory()
    u = UserFactory(organisation=org)
    org.delete()
    u.refresh_from_db()
    assert u.organisation is None


# Task 3: InvitationToken tests
def test_invitation_token_default_expiry_is_48h() -> None:
    org = OrganisationFactory()
    tok = InvitationToken.objects.create(organisation=org, token_hash="a" * 64)
    delta = tok.expires_at - timezone.now()
    assert timedelta(hours=47, minutes=55) < delta < timedelta(hours=48, minutes=5)


def test_invitation_token_is_expired_false_when_future() -> None:
    org = OrganisationFactory()
    tok = InvitationToken.objects.create(
        organisation=org,
        token_hash="b" * 64,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    assert tok.is_expired is False


def test_invitation_token_is_expired_true_when_past() -> None:
    org = OrganisationFactory()
    tok = InvitationToken.objects.create(
        organisation=org,
        token_hash="c" * 64,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    assert tok.is_expired is True


def test_invitation_token_hash_token_is_sha256_hex() -> None:
    digest = InvitationToken.hash_token("abc")
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)


def test_invitation_token_hash_is_unique() -> None:
    org = OrganisationFactory()
    InvitationToken.objects.create(organisation=org, token_hash="d" * 64)
    with pytest.raises(IntegrityError):
        InvitationToken.objects.create(organisation=org, token_hash="d" * 64)
