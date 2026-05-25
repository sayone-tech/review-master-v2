from __future__ import annotations

import re
import secrets as _secrets

import pytest
from django.contrib.auth import authenticate
from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


# -------- AUTH-01: login --------
def test_login_get(anon_client: Client) -> None:
    resp = anon_client.get("/login/")
    assert resp.status_code == 200
    assert b"Sign in" in resp.content


def test_login_post_valid(anon_client: Client, superadmin: User) -> None:
    resp = anon_client.post(
        "/login/", {"username": "super@example.com", "password": "testpass1234"}
    )
    assert resp.status_code == 302
    assert resp.url == "/admin/organisations/"


def test_login_success(anon_client: Client, superadmin: User) -> None:
    resp = anon_client.post(
        "/login/", {"username": "super@example.com", "password": "testpass1234"}, follow=False
    )
    assert resp.status_code == 302
    # Session should now be authenticated
    assert "_auth_user_id" in anon_client.session


def test_login_invalid(anon_client: Client, superadmin: User) -> None:
    resp = anon_client.post("/login/", {"username": "super@example.com", "password": "wrong-pass"})
    # 422 (not 200) — CustomLoginView.form_invalid bumps the status so Hotwire
    # Turbo accepts the re-rendered form instead of throwing "Form responses
    # must redirect to another location".
    assert resp.status_code == 422
    assert b"Incorrect credentials" in resp.content


def test_login_no_enumeration(anon_client: Client) -> None:
    # Nonexistent email returns same error as wrong password
    resp = anon_client.post("/login/", {"username": "nope@example.com", "password": "whatever"})
    assert resp.status_code == 422  # see test_login_invalid for rationale
    assert b"Incorrect credentials" in resp.content
    # Never leak "no such user"
    assert b"does not exist" not in resp.content
    assert b"no account" not in resp.content.lower()


def test_login_rate_limit(anon_client: Client) -> None:
    # 11 failed attempts from same IP → 11th returns 429
    for _ in range(10):
        anon_client.post("/login/", {"username": "x@example.com", "password": "bad"})
    resp = anon_client.post("/login/", {"username": "x@example.com", "password": "bad"})
    assert resp.status_code == 429
    assert b"Too many" in resp.content


def test_login_remember_me(anon_client: Client, superadmin: User) -> None:
    anon_client.post(
        "/login/",
        {"username": "super@example.com", "password": "testpass1234", "remember_me": "on"},
    )
    # 30 days in seconds
    assert anon_client.session.get_expiry_age() == 60 * 60 * 24 * 30


def test_login_no_remember_me(anon_client: Client, superadmin: User) -> None:
    anon_client.post("/login/", {"username": "super@example.com", "password": "testpass1234"})
    # 24 hours in seconds
    assert anon_client.session.get_expiry_age() == 60 * 60 * 24


def test_remember_me(anon_client: Client, superadmin: User) -> None:
    # Alias test covering AUTH-05 remember-me expiry via VALIDATION.md
    anon_client.post(
        "/login/",
        {"username": "super@example.com", "password": "testpass1234", "remember_me": "on"},
    )
    assert anon_client.session.get_expiry_age() == 60 * 60 * 24 * 30


def test_login_next_param(anon_client: Client, superadmin: User) -> None:
    # Role-based redirect wins over next= for SUPERADMIN — they always land on /admin/organisations/
    resp = anon_client.post(
        "/login/?next=/admin/profile/",
        {"username": "super@example.com", "password": "testpass1234", "next": "/admin/profile/"},
    )
    assert resp.status_code == 302
    assert resp.url == "/admin/organisations/"
    # Absolute URLs also redirect to /admin/organisations/ (role override wins either way)
    anon_client.get("/logout/")
    resp2 = anon_client.post(
        "/login/",
        {
            "username": "super@example.com",
            "password": "testpass1234",
            "next": "https://evil.example.com/",
        },
    )
    assert resp2.url == "/admin/organisations/"


# -------- AUTH-02: logout --------
def test_logout(client_logged_in: Client) -> None:
    resp = client_logged_in.post("/logout/")
    assert resp.status_code == 302
    assert resp.url == "/login/"
    assert "_auth_user_id" not in client_logged_in.session


def test_logout_get_rejected(client_logged_in: Client) -> None:
    # Django 5+ LogoutView rejects GET — must not log the user out
    resp = client_logged_in.get("/logout/")
    assert resp.status_code in (405, 302)
    # If 302, it must NOT go to /login/ (which would indicate successful GET logout)
    if resp.status_code == 302:
        assert resp.url != "/login/"


# -------- AUTH-03: password reset request --------
def test_password_reset_email_sent(anon_client: Client, superadmin: User) -> None:
    mail.outbox = []
    resp = anon_client.post("/password-reset/", {"email": "super@example.com"})
    assert resp.status_code == 302
    assert resp.url == "/password-reset/done/"
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "super@example.com" in msg.to
    assert "Reset your password" in msg.subject
    # Multipart: text body + html alternative
    assert any(ct == "text/html" for _, ct in msg.alternatives)


def test_password_reset_no_enumeration(anon_client: Client) -> None:
    mail.outbox = []
    resp = anon_client.post("/password-reset/", {"email": "ghost@example.com"})
    # Always redirects to done page — never reveals whether email exists
    assert resp.status_code == 302
    assert resp.url == "/password-reset/done/"
    assert len(mail.outbox) == 0


# -------- AUTH-04: password reset confirm --------
def test_password_reset_confirm(anon_client: Client, superadmin: User) -> None:
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(superadmin.pk))
    token = default_token_generator.make_token(superadmin)
    # Django's PasswordResetConfirmView validates the token on GET then redirects to "set-password/"
    url = f"/password-reset/confirm/{uid}/{token}/"
    resp = anon_client.get(url, follow=True)
    assert resp.status_code == 200
    # POST new password
    set_url = resp.redirect_chain[-1][0] if resp.redirect_chain else url
    resp2 = anon_client.post(
        set_url, {"new_password1": "NewP@ssword123", "new_password2": "NewP@ssword123"}
    )
    assert resp2.status_code == 302
    superadmin.refresh_from_db()
    assert superadmin.check_password("NewP@ssword123") is True


def test_password_reset_expired(anon_client: Client, superadmin: User, settings) -> None:
    # Force the token to be considered expired by setting timeout to 0 seconds.
    # Django's token check is "(now - ts) > timeout". With timeout=0 we need at
    # least 1 second to pass, so we mock _now() to be 1 second in the future on
    # the check call, making (future - now) == 1 > 0 → expired.
    settings.PASSWORD_RESET_TIMEOUT = 0
    from datetime import datetime, timedelta
    from unittest.mock import patch

    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(superadmin.pk))
    token = default_token_generator.make_token(superadmin)
    future = datetime.now() + timedelta(seconds=1)
    with patch.object(default_token_generator, "_now", return_value=future):
        resp = anon_client.get(f"/password-reset/confirm/{uid}/{token}/", follow=True)
    # Expired tokens render the invalid-link template (200) rather than the form
    assert resp.status_code == 200
    assert b"expired" in resp.content.lower() or b"invalid" in resp.content.lower()


def test_password_reset_redirect(anon_client: Client, superadmin: User) -> None:
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(superadmin.pk))
    token = default_token_generator.make_token(superadmin)
    resp = anon_client.get(f"/password-reset/confirm/{uid}/{token}/")
    # Django redirects to the set-password sub-URL on first GET
    assert resp.status_code == 302
    set_url = resp.url
    final = anon_client.post(
        set_url, {"new_password1": "NewP@ssword123", "new_password2": "NewP@ssword123"}
    )
    # After success, must redirect to /login/ with flash (per CONTEXT.md locked decision:
    # "Password updated. Please sign in.")
    assert final.status_code == 302
    assert final.url == "/login/"


def test_password_reset_flow(anon_client: Client, superadmin: User) -> None:
    # End-to-end: request reset → receive email → follow link → set password → login with new password
    mail.outbox = []
    anon_client.post("/password-reset/", {"email": "super@example.com"})
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body + "".join(alt for alt, _ in mail.outbox[0].alternatives)
    m = re.search(r"/password-reset/confirm/(?P<uid>[^/]+)/(?P<token>[^/\s]+)/", body)
    assert m, f"reset link not found in email body: {body[:300]}"
    path = m.group(0)
    r1 = anon_client.get(path)
    assert r1.status_code == 302
    r2 = anon_client.post(
        r1.url,
        {"new_password1": "NewP@ssword987", "new_password2": "NewP@ssword987"},
    )
    assert r2.status_code == 302
    # New password works
    superadmin.refresh_from_db()
    assert superadmin.check_password("NewP@ssword987") is True
    # Flash message on the redirect response matches the CONTEXT.md locked copy EXACTLY.
    # CustomPasswordResetConfirmView queues this via messages.success(...) in Plan 03 Task 1.
    messages = [str(m) for m in get_messages(r2.wsgi_request)]
    assert "Password updated. Please sign in." in messages, (
        f"Expected flash 'Password updated. Please sign in.' but got: {messages}"
    )


# -------- AUTH-05: session persistence / redirect unauthenticated --------
def test_session_persists(anon_client: Client, superadmin: User) -> None:
    anon_client.post("/login/", {"username": "super@example.com", "password": "testpass1234"})
    # Session cookie has Max-Age set (persistent, not session-only)
    sid_cookie = anon_client.cookies.get("sessionid")
    assert sid_cookie is not None
    assert sid_cookie["max-age"] != ""
    assert int(sid_cookie["max-age"]) > 0


def test_login_required_redirect(anon_client: Client) -> None:
    resp = anon_client.get("/admin/organisations/")
    assert resp.status_code == 302
    # Must redirect to /login/?next=/admin/organisations/
    assert resp.url.startswith("/login/")
    assert (
        "next=%2Fadmin%2Forganisations%2F" in resp.url or "next=/admin/organisations/" in resp.url
    )


def test_redirect_unauthenticated(anon_client: Client) -> None:
    # Alias required by VALIDATION.md task 2-03-02
    resp = anon_client.get("/admin/organisations/")
    assert resp.status_code == 302
    assert "/login/" in resp.url


# -------- Phase 4 Plan 02: EMAL-03 password reset email compliance --------


def test_password_reset_email_emal03_subject_and_body(
    anon_client: Client, superadmin: User
) -> None:
    mail.outbox = []
    resp = anon_client.post("/password-reset/", {"email": "super@example.com"})
    assert resp.status_code == 302  # redirect to done page
    assert len(mail.outbox) == 1
    m = mail.outbox[0]
    # EMAL-03: subject copy
    assert m.subject.strip() == "Reset your password"
    # EMAL-03: 1-hour expiry notice present in body
    assert "1 hour" in m.body
    # EMAL-04: plain-text AND HTML alternative present
    assert m.body, "plain-text body required"
    assert m.alternatives, "HTML alternative required"
    html = m.alternatives[0][0]
    assert "max-width:600px" in html


# --- Phase 4 Plan 03: ActivationForm ---


class TestActivationForm:
    def test_valid(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={
                "full_name": "Jane Smith",
                "password1": "Tr0ub4dor&3xample",
                "password2": "Tr0ub4dor&3xample",
            }
        )
        assert form.is_valid(), form.errors

    def test_full_name_too_short(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={"full_name": "J", "password1": "Tr0ub4dor&3", "password2": "Tr0ub4dor&3"}
        )
        assert not form.is_valid()
        assert "full_name" in form.errors

    def test_full_name_too_long(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={
                "full_name": "x" * 101,
                "password1": "Tr0ub4dor&3",
                "password2": "Tr0ub4dor&3",
            }
        )
        assert not form.is_valid()
        assert "full_name" in form.errors

    def test_password_too_common(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={"full_name": "Jane", "password1": "password", "password2": "password"}
        )
        assert not form.is_valid()
        assert "password1" in form.errors

    def test_password_mismatch(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={
                "full_name": "Jane",
                "password1": "Tr0ub4dor&3",
                "password2": "Different9!",
            }
        )
        assert not form.is_valid()
        assert "password2" in form.errors
        assert "Passwords do not match." in str(form.errors["password2"])

    def test_password_too_short(self) -> None:
        from apps.accounts.forms import ActivationForm

        form = ActivationForm(
            data={"full_name": "Jane", "password1": "Sh0rt!", "password2": "Sh0rt!"}
        )
        assert not form.is_valid()
        assert "password1" in form.errors


# --- Phase 4 Plan 03: invite_accept_view ---


def _create_token(is_used=False, expires_offset_hours=48):
    """Helper: returns (raw_token, invitation) so tests have both values."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import InvitationToken
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory(email=f"org{_secrets.token_hex(3)}@example.com")
    raw = _secrets.token_urlsafe(32)
    inv = InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token(raw),
        is_used=is_used,
        expires_at=timezone.now() + timedelta(hours=expires_offset_hours),
    )
    return raw, inv


def test_invite_accept_valid_get_renders_form(anon_client, db):
    raw, inv = _create_token()
    resp = anon_client.get(f"/invite/accept/{raw}/")
    assert resp.status_code == 200
    assert b"Welcome to " in resp.content
    assert inv.organisation.name.encode() in resp.content
    assert inv.organisation.email.encode() in resp.content
    assert b"disabled" in resp.content
    assert b'name="full_name"' in resp.content
    assert b'name="password1"' in resp.content
    assert b'name="password2"' in resp.content
    assert b"Activate Account" in resp.content


def test_invite_accept_invalid_token_shows_actv04(anon_client, db):
    resp = anon_client.get("/invite/accept/not-a-real-token/")
    assert resp.status_code == 200
    assert b"This invitation link is invalid or has expired." in resp.content
    assert b"Please contact your administrator" in resp.content
    assert b"<form" not in resp.content


def test_invite_accept_used_token_shows_actv05(anon_client, db):
    raw, _ = _create_token(is_used=True)
    resp = anon_client.get(f"/invite/accept/{raw}/")
    assert resp.status_code == 200
    assert b"This invitation has already been used." in resp.content
    assert b"<form" not in resp.content


def test_invite_accept_expired_token_shows_actv04(anon_client, db):
    raw, _ = _create_token(expires_offset_hours=-1)  # already expired
    resp = anon_client.get(f"/invite/accept/{raw}/")
    assert resp.status_code == 200
    assert b"This invitation link is invalid or has expired." in resp.content


def test_invite_accept_used_and_expired_prefers_actv05(anon_client, db):
    raw, _ = _create_token(is_used=True, expires_offset_hours=-1)
    resp = anon_client.get(f"/invite/accept/{raw}/")
    assert resp.status_code == 200
    assert b"This invitation has already been used." in resp.content
    assert b"invalid or has expired" not in resp.content


def test_invite_accept_post_creates_user_and_logs_in(anon_client, db):
    from apps.accounts.models import User

    raw, inv = _create_token()
    resp = anon_client.post(
        f"/invite/accept/{raw}/",
        {
            "full_name": "Jane Admin",
            "password1": "Tr0ub4dor&3",
            "password2": "Tr0ub4dor&3",
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/admin/org-dashboard/"
    assert "_auth_user_id" in anon_client.session
    user = User.objects.get(email=inv.organisation.email)
    assert user.role == User.Role.ORG_ADMIN
    assert user.organisation_id == inv.organisation_id
    assert user.full_name == "Jane Admin"
    inv.refresh_from_db()
    assert inv.is_used is True
    assert inv.invited_user_id == user.id


def test_invite_accept_post_password_mismatch_rerenders_form(anon_client, db):
    from apps.accounts.models import User

    raw, inv = _create_token()
    resp = anon_client.post(
        f"/invite/accept/{raw}/",
        {
            "full_name": "Jane",
            "password1": "Tr0ub4dor&3",
            "password2": "Different9!",
        },
    )
    # 422 (not 200) — Hotwire Turbo accepts 422 as "re-render the form in place".
    # Returning 200 here causes a "Form responses must redirect to another location"
    # error in the browser. See invite_accept_view bottom for the rationale.
    assert resp.status_code == 422
    assert b"Passwords do not match." in resp.content
    assert not User.objects.filter(email=inv.organisation.email).exists()
    inv.refresh_from_db()
    assert inv.is_used is False


def test_invite_accept_post_invalid_password_rerenders_form(anon_client, db):
    from apps.accounts.models import User

    raw, inv = _create_token()
    resp = anon_client.post(
        f"/invite/accept/{raw}/",
        {
            "full_name": "Jane",
            "password1": "password",
            "password2": "password",
        },
    )
    assert resp.status_code == 422  # Hotwire Turbo — see test above for rationale
    # Password validator error should be rendered on form
    assert not User.objects.filter(email=inv.organisation.email).exists()


def test_invite_accept_post_used_token_shows_actv05(anon_client, db):
    raw, _ = _create_token(is_used=True)
    resp = anon_client.post(
        f"/invite/accept/{raw}/",
        {
            "full_name": "Jane",
            "password1": "Tr0ub4dor&3",
            "password2": "Tr0ub4dor&3",
        },
    )
    assert resp.status_code == 200
    assert b"This invitation has already been used." in resp.content


def test_invite_accept_no_login_required_anonymous_ok(anon_client, db):
    raw, _ = _create_token()
    resp = anon_client.get(f"/invite/accept/{raw}/")
    # Must NOT be 302 redirect to /login/
    assert resp.status_code == 200


def test_invite_accept_url_name_resolves():
    from django.urls import reverse

    assert reverse("invite_accept", kwargs={"token": "x"}) == "/invite/accept/x/"


# -------- PROF-01: profile name update --------
class TestProfileNameUpdate:
    def test_profile_get_requires_login(self, anon_client: Client) -> None:
        resp = anon_client.get("/admin/profile/")
        assert resp.status_code == 302
        assert "/login/" in resp.url

    def test_profile_get_authenticated(self, client_logged_in: Client) -> None:
        resp = client_logged_in.get("/admin/profile/")
        assert resp.status_code == 200

    def test_update_name_post_valid(self, client_logged_in: Client, superadmin: User) -> None:
        resp = client_logged_in.post("/admin/profile/update-name/", {"full_name": "New Name"})
        assert resp.status_code == 302
        assert resp.url == "/admin/profile/"
        superadmin.refresh_from_db()
        assert superadmin.full_name == "New Name"
        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        assert any("updated" in m.lower() for m in msgs)

    def test_update_name_post_invalid(self, client_logged_in: Client) -> None:
        resp = client_logged_in.post("/admin/profile/update-name/", {"full_name": "A"})
        # 422 (not 200) — Hotwire Turbo re-render-in-place semantics.
        assert resp.status_code == 422
        assert b"at least 2" in resp.content


# -------- PROF-02: password change --------
class TestPasswordChangeView:
    def test_change_password_post_valid(self, client_logged_in: Client, superadmin: User) -> None:
        resp = client_logged_in.post(
            "/admin/profile/change-password/",
            {
                "current_password": "testpass1234",
                "new_password": "NewStrongPass!2026",
                "confirm_password": "NewStrongPass!2026",
            },
        )
        assert resp.status_code == 302
        assert resp.url == "/admin/profile/"
        superadmin.refresh_from_db()
        assert superadmin.check_password("NewStrongPass!2026")

    def test_change_password_wrong_current(self, client_logged_in: Client) -> None:
        resp = client_logged_in.post(
            "/admin/profile/change-password/",
            {
                "current_password": "wrong-pass",
                "new_password": "NewStrongPass!2026",
                "confirm_password": "NewStrongPass!2026",
            },
        )
        # 422 (not 200) — Hotwire Turbo re-render-in-place semantics.
        assert resp.status_code == 422
        assert b"Current password is incorrect" in resp.content

    def test_change_password_mismatch(self, client_logged_in: Client) -> None:
        resp = client_logged_in.post(
            "/admin/profile/change-password/",
            {
                "current_password": "testpass1234",
                "new_password": "NewStrongPass!2026",
                "confirm_password": "DifferentPass!2026",
            },
        )
        assert resp.status_code == 422  # Hotwire Turbo — see above
        assert b"Passwords do not match" in resp.content

    def test_change_password_session_preserved(self, client_logged_in: Client) -> None:
        resp = client_logged_in.post(
            "/admin/profile/change-password/",
            {
                "current_password": "testpass1234",
                "new_password": "NewStrongPass!2026",
                "confirm_password": "NewStrongPass!2026",
            },
        )
        assert resp.status_code == 302
        # update_session_auth_hash must have kept session alive
        assert "_auth_user_id" in client_logged_in.session


# -------- Phase 6 Plan 03: CustomLoginView role-based redirect --------

_SESSION_AGE_24H = 60 * 60 * 24
_SESSION_AGE_30D = 60 * 60 * 24 * 30


_DEFAULT_PW = "testpass1234"


def _post_login(
    client: Client, email: str, password: str = _DEFAULT_PW, remember: bool = False
) -> object:
    data: dict = {"username": email, "password": password}
    if remember:
        data["remember_me"] = "on"
    return client.post("/login/", data, follow=False)


def test_login_redirect_superadmin_to_organisations() -> None:
    from apps.accounts.tests.factories import UserFactory

    UserFactory(
        email="sa-redirect@example.com",
        role=User.Role.SUPERADMIN,
        password="testpass1234",
    )
    client = Client()
    response = _post_login(client, "sa-redirect@example.com")
    assert response.status_code == 302
    assert response["Location"] == "/admin/organisations/"


def test_login_redirect_org_admin_with_org_to_dashboard() -> None:
    from apps.accounts.tests.factories import UserFactory
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory()
    UserFactory(
        email="oa-redirect@example.com",
        role=User.Role.ORG_ADMIN,
        organisation=org,
        password="testpass1234",
    )
    client = Client()
    response = _post_login(client, "oa-redirect@example.com")
    assert response.status_code == 302
    assert response["Location"] == "/admin/org/dashboard/"


def test_login_redirect_org_admin_without_org_falls_back() -> None:
    from django.conf import settings

    from apps.accounts.tests.factories import UserFactory

    UserFactory(
        email="oa-noorg@example.com",
        role=User.Role.ORG_ADMIN,
        organisation=None,
        password="testpass1234",
    )
    client = Client()
    response = _post_login(client, "oa-noorg@example.com")
    assert response.status_code == 302
    assert response["Location"] == settings.LOGIN_REDIRECT_URL


def test_login_redirect_staff_admin_falls_back() -> None:
    from django.conf import settings

    from apps.accounts.tests.factories import UserFactory
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory()
    UserFactory(
        email="staff-redirect@example.com",
        role=User.Role.STAFF_ADMIN,
        organisation=org,
        password="testpass1234",
    )
    client = Client()
    response = _post_login(client, "staff-redirect@example.com")
    assert response.status_code == 302
    assert response["Location"] == settings.LOGIN_REDIRECT_URL


def test_login_remember_me_unchecked_sets_24h_expiry() -> None:
    from apps.accounts.tests.factories import UserFactory
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory()
    UserFactory(
        email="oa-24h@example.com",
        role=User.Role.ORG_ADMIN,
        organisation=org,
        password="testpass1234",
    )
    client = Client()
    _post_login(client, "oa-24h@example.com", remember=False)
    assert client.session.get_expiry_age() == _SESSION_AGE_24H


def test_login_remember_me_checked_sets_30d_expiry() -> None:
    from apps.accounts.tests.factories import UserFactory
    from apps.organisations.tests.factories import OrganisationFactory

    org = OrganisationFactory()
    UserFactory(
        email="oa-30d@example.com",
        role=User.Role.ORG_ADMIN,
        organisation=org,
        password="testpass1234",
    )
    client = Client()
    _post_login(client, "oa-30d@example.com", remember=True)
    assert client.session.get_expiry_age() == _SESSION_AGE_30D


# -------- Phase 6 Plan 05: Org Admin profile (SHEL-04) --------


def _org_admin_login(password: str = "testpass1234"):  # noqa: S107
    """Create an ORG_ADMIN with organisation and return (client, user, org)."""
    org = OrganisationFactory()
    user = UserFactory(
        role=User.Role.ORG_ADMIN,
        organisation=org,
        full_name="Original Name",
        email="orgprofile@example.com",
        password=password,
    )
    client = Client()
    client.force_login(user)
    return client, user, org


def test_org_profile_get_returns_200_with_two_cards() -> None:
    client, user, _ = _org_admin_login()
    response = client.get("/admin/org/profile/")
    assert response.status_code == 200
    assert b"Your profile" in response.content
    assert b"Change password" in response.content
    assert user.email.encode() in response.content


def test_org_profile_renders_inside_base_org_shell() -> None:
    """Confirm sidebar partial from base_org.html is rendered."""
    client, _, _ = _org_admin_login()
    response = client.get("/admin/org/profile/")
    assert response.status_code == 200
    # base_org.html includes shell_org_open which includes sidebar_org with data-testid="sidebar"
    assert b'data-testid="sidebar"' in response.content


def test_org_profile_redirects_superadmin() -> None:
    user = UserFactory(role=User.Role.SUPERADMIN)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/org/profile/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/organisations/"


def test_org_profile_accessible_to_staff_admin() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/org/profile/")
    assert response.status_code == 200


def test_org_profile_redirects_org_admin_without_organisation_to_login() -> None:
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=None)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/org/profile/")
    assert response.status_code == 302
    assert response["Location"] == "/login/"


def test_org_profile_update_name_success() -> None:
    client, user, _ = _org_admin_login()
    response = client.post(
        "/admin/org/profile/update-name/",
        {"full_name": "Updated Org Admin Name"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/admin/org/profile/"
    user.refresh_from_db()
    assert user.full_name == "Updated Org Admin Name"


def test_org_profile_update_name_invalid_renders_form_with_error() -> None:
    client, user, _ = _org_admin_login()
    response = client.post(
        "/admin/org/profile/update-name/",
        {"full_name": "X"},  # too short (min 2 chars)
    )
    # 422 (not 200) so Hotwire Turbo accepts the re-rendered form.
    assert response.status_code == 422
    # Original name unchanged
    user.refresh_from_db()
    assert user.full_name == "Original Name"


def test_org_profile_change_password_success() -> None:
    client, user, _ = _org_admin_login(password="testpass1234")
    response = client.post(
        "/admin/org/profile/change-password/",
        {
            "current_password": "testpass1234",
            "new_password": "newtestpass2345",
            "confirm_password": "newtestpass2345",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == "/admin/org/profile/"
    # New password works
    assert authenticate(username=user.email, password="newtestpass2345") is not None


def test_org_profile_change_password_wrong_current_shows_error() -> None:
    client, user, _ = _org_admin_login(password="testpass1234")
    response = client.post(
        "/admin/org/profile/change-password/",
        {
            "current_password": "WRONG-PASSWORD",
            "new_password": "newtestpass2345",
            "confirm_password": "newtestpass2345",
        },
    )
    # 422 (not 200) so Hotwire Turbo accepts the re-rendered form.
    assert response.status_code == 422
    assert b"Current password is incorrect." in response.content
    # Original password still works
    assert authenticate(username=user.email, password="testpass1234") is not None


def test_existing_superadmin_profile_url_still_works() -> None:
    """No regression: /admin/profile/ continues to render the Phase 5 profile."""
    user = UserFactory(role=User.Role.SUPERADMIN)
    client = Client()
    client.force_login(user)
    response = client.get("/admin/profile/")
    assert response.status_code == 200


def test_org_profile_url_names_resolve_correctly() -> None:
    assert reverse("org_profile") == "/admin/org/profile/"
    assert reverse("org_profile_update_name") == "/admin/org/profile/update-name/"
    assert reverse("org_profile_change_password") == "/admin/org/profile/change-password/"
