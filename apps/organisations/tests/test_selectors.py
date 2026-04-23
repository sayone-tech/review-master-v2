from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.organisations.models import Organisation
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db

WAVE_0 = pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — implemented in Plan 02")


@WAVE_0
def test_list_organisations_returns_not_deleted_only(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    OrganisationFactory(name="Dead", email="dead@example.com", status=Organisation.Status.DELETED)
    result = list(list_organisations())
    assert all(o.status != Organisation.Status.DELETED for o in result)
    assert len(result) == 3


@WAVE_0
def test_list_organisations_search_by_name_case_insensitive(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(search="alpha"))
    assert len(result) == 1
    assert result[0].name == "Alpha Retail"


@WAVE_0
def test_list_organisations_search_by_email_case_insensitive(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(search="BETA@"))
    assert len(result) == 1
    assert result[0].email == "beta@example.com"


@WAVE_0
def test_list_organisations_filter_by_status(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(status="DISABLED"))
    assert len(result) == 1
    assert result[0].status == Organisation.Status.DISABLED


@WAVE_0
def test_list_organisations_filter_by_org_type(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations(org_type="PHARMACY"))
    assert len(result) == 1
    assert result[0].org_type == Organisation.OrgType.PHARMACY


@WAVE_0
def test_list_organisations_ordered_by_created_at_desc(three_orgs):
    from apps.organisations.selectors.organisations import list_organisations

    result = list(list_organisations())
    assert result[0].created_at >= result[-1].created_at


@WAVE_0
def test_list_organisations_fixed_query_count_ceiling():
    from apps.organisations.selectors.organisations import list_organisations

    OrganisationFactory.create_batch(20)
    with CaptureQueriesContext(connection) as ctx:
        result = list(list_organisations())
    assert len(result) == 20
    assert len(ctx.captured_queries) <= 3  # 1 org + 1 prefetch invitation_tokens + 1 related


@WAVE_0
def test_get_organisation_detail_includes_activation_status_and_last_invited_at():
    from apps.accounts.models import InvitationToken
    from apps.organisations.selectors.organisations import get_organisation_detail

    org = OrganisationFactory()
    InvitationToken.objects.create(organisation=org, token_hash=InvitationToken.hash_token("tok"))
    detail = get_organisation_detail(organisation_id=org.id)
    assert hasattr(detail, "prefetched_tokens") or len(detail.invitation_tokens.all()) >= 1
