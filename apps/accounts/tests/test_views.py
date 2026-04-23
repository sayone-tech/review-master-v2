from __future__ import annotations

import re
import secrets as _secrets

import pytest
from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client

from apps.accounts.models import User

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
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.content


def test_login_no_enumeration(anon_client: Client) -> None:
    # Nonexistent email returns same error as wrong password
    resp = anon_client.post("/login/", {"username": "nope@example.com", "password": "whatever"})
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.content
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
    resp = anon_client.post(
        "/login/?next=/admin/profile/",
        {"username": "super@example.com", "password": "testpass1234", "next": "/admin/profile/"},
    )
    assert resp.status_code == 302
    assert resp.url == "/admin/profile/"
    # Absolute URLs rejected → falls back to LOGIN_REDIRECT_URL
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
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
