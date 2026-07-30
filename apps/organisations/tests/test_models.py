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


def test_annotate_store_counts_zero_when_no_shops() -> None:
    """SA-056: an org with no shops reports zero total and active."""
    OrganisationFactory()
    org = Organisation.objects.annotate_store_counts().first()
    assert org is not None
    assert org.total_stores == 0
    assert org.active_stores == 0


def test_annotate_store_counts_reflects_real_shops() -> None:
    """SA-056: total_stores counts all shops; active_stores counts only is_active."""
    from apps.shops.tests.factories import ShopFactory

    org = OrganisationFactory()
    ShopFactory.create_batch(2, organisation=org, is_active=True)
    ShopFactory(organisation=org, is_active=False)
    # Another org's shop must not leak into this org's counts.
    ShopFactory(organisation=OrganisationFactory())

    annotated = Organisation.objects.annotate_store_counts().get(id=org.id)
    assert annotated.total_stores == 3
    assert annotated.active_stores == 2


def test_organisation_allow_custom_sync_depth_default_false(db) -> None:
    org = OrganisationFactory()
    assert org.allow_custom_sync_depth is False


def test_organisation_allow_custom_sync_depth_can_be_set_true(db) -> None:
    org = OrganisationFactory(allow_custom_sync_depth=True)
    org.refresh_from_db()
    assert org.allow_custom_sync_depth is True
