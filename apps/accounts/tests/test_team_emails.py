from __future__ import annotations

import pytest
from django.core import mail

from apps.accounts.models import StaffAccessScope
from apps.accounts.services.team import send_team_invitation_email
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAccessScopeFactory,
    StaffAdminFactory,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_team_invitation_email_manager_omits_scopes(settings):
    settings.SITE_URL = "https://example.com"
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org, full_name="Sam Inviter")
    member = OrgAdminFactory(organisation=org, full_name="Pat Manager", email="pat@acme.test")
    send_team_invitation_email(
        member=member,
        raw_token="abc123",
        inviter=inviter,
        scopes=[],
        is_resend=False,
    )
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.subject == "You're invited to join Acme Co"
    assert msg.to == ["pat@acme.test"]
    html = msg.alternatives[0][0]
    assert "Pat Manager" in html
    assert "Sam Inviter" in html
    assert "Manager" in html
    assert "abc123" in html
    assert "48 hours" in html
    assert "Regions:" not in html
    assert "Stores:" not in html
    assert "{{" not in html  # template fully rendered
    text = msg.body
    assert "Pat Manager" in text
    assert "Sam Inviter" in text
    assert "abc123" in text


@pytest.mark.django_db
def test_team_invitation_email_staff_lists_scopes(settings):
    settings.SITE_URL = "https://example.com"
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org, full_name="Sam Inviter")
    r1 = RegionFactory(organisation=org, name="North")
    r2 = RegionFactory(organisation=org, name="South")
    shop = ShopFactory(organisation=org, name="Flagship", region=r1)
    member = StaffAdminFactory(organisation=org, full_name="Lee Staff", email="lee@acme.test")
    scopes = [
        StaffAccessScopeFactory(
            user=member,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=r1,
            shop=None,
        ),
        StaffAccessScopeFactory(
            user=member,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=r2,
            shop=None,
        ),
        StaffAccessScopeFactory(
            user=member,
            scope_type=StaffAccessScope.ScopeType.SHOP,
            region=None,
            shop=shop,
        ),
    ]
    send_team_invitation_email(
        member=member,
        raw_token="xyz",
        inviter=inviter,
        scopes=scopes,
        is_resend=False,
    )
    html = mail.outbox[0].alternatives[0][0]
    assert "Regions:" in html
    assert "North" in html
    assert "South" in html
    assert "Stores:" in html
    assert "Flagship" in html
    text = mail.outbox[0].body
    assert "North" in text
    assert "South" in text
    assert "Flagship" in text


@pytest.mark.django_db
def test_team_invitation_email_resent_subject_and_notice(settings):
    settings.SITE_URL = "https://example.com"
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org, full_name="Sam Inviter")
    member = StaffAdminFactory(organisation=org, full_name="Lee Staff", email="lee@acme.test")
    send_team_invitation_email(
        member=member,
        raw_token="t",
        inviter=inviter,
        scopes=[],
        is_resend=True,
    )
    msg = mail.outbox[0]
    assert msg.subject == "New invitation link for Acme Co"
    html = msg.alternatives[0][0]
    assert "This replaces any previous invitation. The earlier link is no longer valid." in html
    assert "This replaces any previous invitation. The earlier link is no longer valid." in msg.body


@pytest.mark.django_db
def test_team_invitation_email_initial_omits_resent_notice():
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, email="lee@acme.test")
    send_team_invitation_email(
        member=member,
        raw_token="t",
        inviter=inviter,
        scopes=[],
        is_resend=False,
    )
    html = mail.outbox[0].alternatives[0][0]
    assert "earlier link is no longer valid" not in html


@pytest.mark.django_db
def test_team_invitation_template_uses_brand_yellow():
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, email="x@y.test")
    send_team_invitation_email(
        member=member,
        raw_token="t",
        inviter=inviter,
        scopes=[],
        is_resend=False,
    )
    html = mail.outbox[0].alternatives[0][0]
    assert "#FACC15" in html


@pytest.mark.django_db
def test_team_invitation_template_max_width_600():
    org = OrganisationFactory(name="Acme Co")
    inviter = OrgAdminFactory(organisation=org)
    member = StaffAdminFactory(organisation=org, email="x@y.test")
    send_team_invitation_email(
        member=member,
        raw_token="t",
        inviter=inviter,
        scopes=[],
        is_resend=False,
    )
    html = mail.outbox[0].alternatives[0][0]
    assert 'width="600"' in html
    assert "max-width:600px" in html
