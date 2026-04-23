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


# --- Phase 4 Plan 02: absolute accept URL ---


def test_build_accept_url_returns_absolute_url():
    from apps.organisations.services.organisations import _build_accept_url

    url = _build_accept_url("abc123token")
    assert url.startswith("http://") or url.startswith("https://")
    assert url.endswith("/invite/accept/abc123token/")


def test_build_accept_url_default_site_url():
    from django.conf import settings

    from apps.organisations.services.organisations import _build_accept_url

    assert settings.SITE_URL == "http://localhost:8000"
    assert _build_accept_url("tok") == "http://localhost:8000/invite/accept/tok/"


def test_build_accept_url_strips_trailing_slash_in_site_url(settings):
    from apps.organisations.services.organisations import _build_accept_url

    settings.SITE_URL = "https://reviewmaster.example.com/"
    assert _build_accept_url("tok") == "https://reviewmaster.example.com/invite/accept/tok/"


def test_create_organisation_invitation_email_contains_absolute_url(superadmin):
    import re

    from django.core import mail

    from apps.organisations.services.organisations import create_organisation

    create_organisation(
        name="Absolute Co",
        org_type="RETAIL",
        email="abs@example.com",
        address="",
        number_of_stores=1,
        created_by=superadmin,
    )
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    # HTML alternative
    html_body = m.alternatives[0][0] if m.alternatives else ""
    assert (
        "http://localhost:8000/invite/accept/" in m.body
        or "http://localhost:8000/invite/accept/" in html_body
    )
    # Ensure NOT just a relative path leaking into either body
    assert not re.search(r'href="/invite/accept/', html_body), "HTML email must use absolute URL"


# --- Phase 4 Plan 02: is_resend template conditional ---


def _render_invitation(context):
    from django.template.loader import render_to_string

    ctx = {"expires_in_hours": 48, "accept_url": "http://x/invite/accept/t/", **context}
    return (
        render_to_string("emails/invitation.html", ctx),
        render_to_string("emails/invitation.txt", ctx),
    )


def test_invitation_html_renders_resend_note_when_is_resend_true(db):
    org = OrganisationFactory(name="ResendCo")
    html, _ = _render_invitation({"organisation": org, "is_resend": True})
    assert "This replaces any previous invitation." in html


def test_invitation_html_omits_resend_note_by_default(db):
    org = OrganisationFactory(name="FirstCo")
    html, _ = _render_invitation({"organisation": org})
    assert "This replaces any previous invitation." not in html


def test_invitation_html_omits_resend_note_when_is_resend_false(db):
    org = OrganisationFactory(name="FalseCo")
    html, _ = _render_invitation({"organisation": org, "is_resend": False})
    assert "This replaces any previous invitation." not in html


def test_invitation_txt_renders_resend_note_when_is_resend_true(db):
    org = OrganisationFactory(name="TxtResendCo")
    _, txt = _render_invitation({"organisation": org, "is_resend": True})
    assert "This replaces any previous invitation." in txt


def test_invitation_txt_omits_resend_note_by_default(db):
    org = OrganisationFactory(name="TxtFirstCo")
    _, txt = _render_invitation({"organisation": org})
    assert "This replaces any previous invitation." not in txt


# --- EMAL-04 compliance audit ---


def test_invitation_html_emal04_compliance():
    from pathlib import Path

    from django.conf import settings

    p = Path(settings.BASE_DIR) / "templates" / "emails" / "invitation.html"
    content = p.read_text()
    assert "max-width:600px" in content
    assert "<style" not in content.lower(), "invitation.html must use inline styles only"


def test_invitation_txt_plaintext_sibling_exists():
    from pathlib import Path

    from django.conf import settings

    p = Path(settings.BASE_DIR) / "templates" / "emails" / "invitation.txt"
    assert p.exists()
    assert p.stat().st_size > 0


def test_password_reset_html_emal04_compliance():
    from pathlib import Path

    from django.conf import settings

    p = Path(settings.BASE_DIR) / "templates" / "emails" / "password_reset.html"
    content = p.read_text()
    assert "max-width:600px" in content
    assert "<style" not in content.lower(), "password_reset.html must use inline styles only"
    assert "1 hour" in content


def test_password_reset_txt_plaintext_sibling_exists():
    from pathlib import Path

    from django.conf import settings

    p = Path(settings.BASE_DIR) / "templates" / "emails" / "password_reset.txt"
    assert p.exists()
    assert p.stat().st_size > 0


# --- Phase 4 Plan 04: resend_invitation service ---


def test_resend_invitation_creates_token_when_none_exists(db, superadmin):
    from apps.accounts.models import InvitationToken
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="none@example.com")
    assert InvitationToken.objects.filter(organisation=org).count() == 0

    raw = resend_invitation(organisation=org, resent_by=superadmin)

    assert isinstance(raw, str)
    assert len(raw) > 0
    assert InvitationToken.objects.filter(organisation=org, is_used=False).count() == 1


def test_resend_invitation_invalidates_existing_nonused_tokens(db, superadmin):
    from apps.accounts.models import InvitationToken
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="old@example.com")
    old = InvitationTokenFactory(organisation=org, is_used=False)

    resend_invitation(organisation=org, resent_by=superadmin)

    old.refresh_from_db()
    assert old.is_used is True
    assert InvitationToken.objects.filter(organisation=org).count() == 2
    assert InvitationToken.objects.filter(organisation=org, is_used=False).count() == 1


def test_resend_invitation_invalidates_multiple_old_tokens(db, superadmin):
    from apps.accounts.models import InvitationToken
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="multi@example.com")
    InvitationTokenFactory.create_batch(2, organisation=org, is_used=False)

    resend_invitation(organisation=org, resent_by=superadmin)

    assert InvitationToken.objects.filter(organisation=org).count() == 3
    assert InvitationToken.objects.filter(organisation=org, is_used=False).count() == 1


def test_resend_invitation_leaves_used_tokens_alone(db, superadmin):
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="left-alone@example.com")
    already_used = InvitationTokenFactory(organisation=org, is_used=True)

    resend_invitation(organisation=org, resent_by=superadmin)

    already_used.refresh_from_db()
    assert already_used.is_used is True  # unchanged, still used


def test_resend_invitation_sends_email_with_resend_marker(db, superadmin):
    from django.core import mail

    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(name="Resend Co", email="resendco@example.com")
    resend_invitation(organisation=org, resent_by=superadmin)

    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    assert m.to == ["resendco@example.com"]
    assert m.subject == "You're invited to manage Resend Co"
    assert "This replaces any previous invitation." in m.body  # plain text
    assert m.alternatives, "HTML alternative must be present"
    html = m.alternatives[0][0]
    assert "This replaces any previous invitation." in html


def test_resend_invitation_email_accept_url_is_absolute_and_new_token(db, superadmin):
    from django.core import mail

    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="absnew@example.com")
    raw = resend_invitation(organisation=org, resent_by=superadmin)

    m = mail.outbox[0]
    html = m.alternatives[0][0]
    # absolute URL present
    assert "http://" in html or "https://" in html
    # new raw token appears in both text and HTML bodies
    assert raw in m.body
    assert raw in html


def test_resend_invitation_atomic_rollback_if_email_fails(db, superadmin, monkeypatch):
    from apps.accounts.models import InvitationToken
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="rollback@example.com")
    old = InvitationTokenFactory(organisation=org, is_used=False)

    def boom(**kwargs):
        raise RuntimeError("SES down")

    monkeypatch.setattr("apps.organisations.services.organisations.send_transactional_email", boom)

    with pytest.raises(RuntimeError):
        resend_invitation(organisation=org, resent_by=superadmin)

    old.refresh_from_db()
    assert old.is_used is False, "atomic rollback must restore old token is_used state"
    assert InvitationToken.objects.filter(organisation=org).count() == 1, "no new token persisted"


def test_resend_invitation_old_token_shows_actv05_after_resend(db, superadmin, client):
    """Integration: after resend, visiting the OLD invite URL returns ACTV-05."""
    import secrets as _s

    from apps.accounts.models import InvitationToken
    from apps.organisations.services.organisations import resend_invitation
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email="old-link@example.com")
    old_raw = _s.token_urlsafe(32)
    InvitationToken.objects.create(organisation=org, token_hash=InvitationToken.hash_token(old_raw))

    resend_invitation(organisation=org, resent_by=superadmin)

    resp = client.get(f"/invite/accept/{old_raw}/")
    assert resp.status_code == 200
    assert b"This invitation has already been used." in resp.content


# --- Phase 4 Plan 03: activate_account service ---


def test_activate_account_creates_org_admin_user(db, superadmin):
    from apps.accounts.models import User
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import activate_account

    org = OrganisationFactory(email="activate@example.com")
    token = InvitationTokenFactory(organisation=org)

    user = activate_account(invitation=token, full_name="Jane A", password="Tr0ub4dor&3")

    assert isinstance(user, User)
    assert user.email == "activate@example.com"
    assert user.role == User.Role.ORG_ADMIN
    assert user.organisation_id == org.id
    assert user.full_name == "Jane A"
    assert user.check_password("Tr0ub4dor&3")
    token.refresh_from_db()
    assert token.is_used is True
    assert token.invited_user_id == user.id


def test_activate_account_already_used_raises(db):
    from django.core.exceptions import ValidationError

    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import activate_account

    org = OrganisationFactory(email="used@example.com")
    token = InvitationTokenFactory(organisation=org, is_used=True)

    with pytest.raises(ValidationError):
        activate_account(invitation=token, full_name="X", password="Tr0ub4dor&3")


def test_activate_account_atomic_on_create_failure(db, monkeypatch):
    from django.db import IntegrityError

    from apps.accounts.managers import UserManager
    from apps.accounts.tests.factories import InvitationTokenFactory
    from apps.organisations.services.organisations import activate_account

    org = OrganisationFactory(email="atomic@example.com")
    token = InvitationTokenFactory(organisation=org)

    def boom(self, *a, **k):
        raise IntegrityError("forced")

    monkeypatch.setattr(UserManager, "create_user", boom)

    with pytest.raises(IntegrityError):
        activate_account(invitation=token, full_name="X", password="Tr0ub4dor&3")

    token.refresh_from_db()
    assert token.is_used is False, "token must not be marked used if user creation failed (atomic)"
