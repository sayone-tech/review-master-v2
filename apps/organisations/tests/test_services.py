from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core import mail

from apps.organisations.models import Organisation
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def test_create_organisation_persists_row(superadmin):
    from apps.organisations.services.organisations import create_organisation

    org, _token = create_organisation(
        name="New Co",
        org_type="RETAIL",
        email="new@example.com",
        address="",
        number_of_stores=5,
        created_by=superadmin,
    )
    assert Organisation.objects.filter(id=org.id, email="new@example.com").exists()


def test_create_organisation_creates_invitation_token(superadmin):
    from apps.accounts.models import InvitationToken
    from apps.organisations.services.organisations import create_organisation

    org, _ = create_organisation(
        name="A",
        org_type="RETAIL",
        email="a@b.com",
        address="",
        number_of_stores=1,
        created_by=superadmin,
    )
    assert InvitationToken.objects.filter(organisation=org, is_used=False).exists()


def test_create_organisation_sends_invitation_email(superadmin):
    from apps.organisations.services.organisations import create_organisation

    create_organisation(
        name="Acme",
        org_type="RETAIL",
        email="new@example.com",
        address="",
        number_of_stores=1,
        created_by=superadmin,
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.to == ["new@example.com"]
    assert "Acme" in m.subject


def test_create_organisation_atomic_rollback_if_email_fails(superadmin):
    from apps.organisations.services.organisations import create_organisation

    with (
        patch(
            "apps.organisations.services.organisations.send_transactional_email",
            side_effect=RuntimeError("SMTP down"),
        ),
        pytest.raises(RuntimeError),
    ):
        create_organisation(
            name="Rollback",
            org_type="RETAIL",
            email="rb@example.com",
            address="",
            number_of_stores=1,
            created_by=superadmin,
        )
    assert not Organisation.objects.filter(email="rb@example.com").exists()


def test_update_organisation_does_not_change_email():
    from apps.organisations.services.organisations import update_organisation

    org = OrganisationFactory(email="original@example.com")
    update_organisation(organisation=org, name="Renamed", email="attempt@example.com")
    org.refresh_from_db()
    assert org.email == "original@example.com"
    assert org.name == "Renamed"


def test_update_organisation_modifies_other_fields():
    from apps.organisations.services.organisations import update_organisation

    org = OrganisationFactory(number_of_stores=5)
    update_organisation(organisation=org, number_of_stores=20, address="New addr")
    org.refresh_from_db()
    assert org.number_of_stores == 20
    assert org.address == "New addr"


def test_disable_organisation_sets_status_disabled():
    from apps.organisations.services.organisations import disable_organisation

    org = OrganisationFactory(status=Organisation.Status.ACTIVE)
    disable_organisation(organisation=org)
    org.refresh_from_db()
    assert org.status == Organisation.Status.DISABLED


def test_enable_organisation_sets_status_active():
    from apps.organisations.services.organisations import enable_organisation

    org = OrganisationFactory(status=Organisation.Status.DISABLED)
    enable_organisation(organisation=org)
    org.refresh_from_db()
    assert org.status == Organisation.Status.ACTIVE


def test_delete_organisation_soft_deletes_not_hard():
    from apps.organisations.services.organisations import delete_organisation

    org = OrganisationFactory()
    org_id = org.id
    delete_organisation(organisation=org)
    assert Organisation.objects.filter(id=org_id, status=Organisation.Status.DELETED).exists()


def test_adjust_store_allocation_updates_number_of_stores():
    from apps.organisations.services.organisations import adjust_store_allocation

    org = OrganisationFactory(number_of_stores=5)
    adjust_store_allocation(organisation=org, new_allocation=15)
    org.refresh_from_db()
    assert org.number_of_stores == 15


def test_adjust_store_allocation_rejects_zero():
    from django.core.exceptions import ValidationError

    from apps.organisations.services.organisations import adjust_store_allocation

    org = OrganisationFactory(number_of_stores=5)
    with pytest.raises(ValidationError):
        adjust_store_allocation(organisation=org, new_allocation=0)


def test_update_organisation_strips_email_even_if_passed():
    from apps.organisations.services.organisations import update_organisation

    org = OrganisationFactory(email="original@example.com")
    update_organisation(organisation=org, email="hack@example.com", name="Renamed")
    org.refresh_from_db()
    assert org.email == "original@example.com"
    assert org.name == "Renamed"
