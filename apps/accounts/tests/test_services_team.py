from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_invite_member():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_invite_member_sends_email():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_disable_member():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_enable_member():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_remove_member():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_remove_member_invalidates_pending_tokens():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_remove_member_last_manager_guard():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_resend_team_invitation():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_resend_nulls_old_token_invited_user():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_activate_team_member():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_team_invitation_email():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_team_invitation_resent_email():
    pytest.skip("implemented in Task 2")


@pytest.mark.django_db
def test_update_member_replaces_scopes():
    pytest.skip("implemented in Task 2")
