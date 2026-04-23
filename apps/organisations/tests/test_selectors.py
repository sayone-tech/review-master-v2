from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import InvitationToken
from apps.organisations.models import Organisation
from apps.organisations.selectors.organisations import activation_status_for, list_organisations
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def test_list_organisations_returns_not_deleted_only(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    OrganisationFactory(name="Dead", email="dead@example.com", status=Organisation.Status.DELETED)
    result = list(list_organisations())
    assert all(o.status != Organisation.Status.DELETED for o in result)
    assert len(result) == 3


def test_list_organisations_search_by_name_case_insensitive(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(search="alpha"))
    assert len(result) == 1
    assert result[0].name == "Alpha Retail"


def test_list_organisations_search_by_email_case_insensitive(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(search="BETA@"))
    assert len(result) == 1
    assert result[0].email == "beta@example.com"


def test_list_organisations_filter_by_status(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(status="DISABLED"))
    assert len(result) == 1
    assert result[0].status == Organisation.Status.DISABLED


def test_list_organisations_filter_by_org_type(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(org_type="PHARMACY"))
    assert len(result) == 1
    assert result[0].org_type == Organisation.OrgType.PHARMACY


def test_list_organisations_ordered_by_created_at_desc(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations())
    assert result[0].created_at >= result[-1].created_at


def test_list_organisations_fixed_query_count_ceiling():
    from apps.organisations.selectors.organisations import list_organisations

    OrganisationFactory.create_batch(20)
    with CaptureQueriesContext(connection) as ctx:
        result = list(list_organisations())
    assert len(result) == 20
    assert len(ctx.captured_queries) <= 3  # 1 org + 1 prefetch invitation_tokens + 1 related


def test_get_organisation_detail_includes_activation_status_and_last_invited_at():
    from apps.accounts.models import InvitationToken
    from apps.organisations.selectors.organisations import (
        activation_status_for,
        get_organisation_detail,
        last_invited_at_for,
    )

    org = OrganisationFactory()
    InvitationToken.objects.create(organisation=org, token_hash=InvitationToken.hash_token("tok"))
    detail = get_organisation_detail(organisation_id=org.id)
    assert activation_status_for(detail) == "pending"
    assert last_invited_at_for(detail) is not None


def test_activation_status_returns_pending_when_no_tokens():
    org = OrganisationFactory()
    # re-fetch via selector to get prefetched_tokens attribute
    loaded = list_organisations().filter(id=org.id).first()
    assert activation_status_for(loaded) == "pending"


def test_activation_status_returns_active_when_a_token_is_used():
    org = OrganisationFactory()
    InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token("a"),
        is_used=True,
    )
    loaded = list_organisations().filter(id=org.id).first()
    assert activation_status_for(loaded) == "active"


def test_activation_status_returns_expired_when_latest_unused_token_is_past_expiry():
    org = OrganisationFactory()
    t = InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token("b"),
        is_used=False,
    )
    t.expires_at = timezone.now() - timedelta(hours=1)
    t.save(update_fields=["expires_at"])
    loaded = list_organisations().filter(id=org.id).first()
    assert activation_status_for(loaded) == "expired"
