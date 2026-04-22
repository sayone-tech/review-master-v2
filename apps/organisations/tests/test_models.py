import pytest
from django.db import IntegrityError

from apps.organisations.models import Organisation
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def test_status_enum_values() -> None:
    assert set(Organisation.Status.values) == {"ACTIVE", "DISABLED", "DELETED"}


def test_org_type_enum_values() -> None:
    assert set(Organisation.OrgType.values) == {"RETAIL", "RESTAURANT", "PHARMACY", "SUPERMARKET"}


def test_default_status_is_active() -> None:
    org = OrganisationFactory()
    assert org.status == Organisation.Status.ACTIVE


def test_duplicate_email_raises_integrity_error() -> None:
    Organisation.objects.create(
        name="Dup Org",
        email="dup@example.com",
        org_type=Organisation.OrgType.RETAIL,
        number_of_stores=1,
    )
    with pytest.raises(IntegrityError):
        Organisation.objects.create(
            name="Dup Org 2",
            email="dup@example.com",
            org_type=Organisation.OrgType.RETAIL,
            number_of_stores=1,
        )


def test_soft_delete_sets_status_to_deleted() -> None:
    org = OrganisationFactory()
    org.soft_delete()
    org.refresh_from_db()
    assert org.status == Organisation.Status.DELETED


def test_active_queryset_filter() -> None:
    OrganisationFactory(status=Organisation.Status.ACTIVE)
    OrganisationFactory(email="disabled@example.com", status=Organisation.Status.DISABLED)
    OrganisationFactory(email="deleted@example.com", status=Organisation.Status.DELETED)
    assert Organisation.objects.active().count() == 1


def test_deleted_queryset_filter() -> None:
    OrganisationFactory(status=Organisation.Status.DELETED)
    OrganisationFactory(email="active@example.com", status=Organisation.Status.ACTIVE)
    assert Organisation.objects.deleted().count() == 1


def test_not_deleted_queryset_filter() -> None:
    OrganisationFactory(status=Organisation.Status.DELETED)
    OrganisationFactory(email="active@example.com", status=Organisation.Status.ACTIVE)
    OrganisationFactory(email="disabled@example.com", status=Organisation.Status.DISABLED)
    assert Organisation.objects.not_deleted().count() == 2


def test_annotate_store_counts_returns_zero_in_phase_1() -> None:
    """Phase 1 stub: store counts always zero until Phase 2 adds Store model."""
    OrganisationFactory()
    org = Organisation.objects.annotate_store_counts().first()
    assert org is not None
    assert org.total_stores == 0
    assert org.active_stores == 0
