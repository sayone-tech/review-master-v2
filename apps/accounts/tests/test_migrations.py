from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from apps.accounts.models import InvitationToken


@pytest.mark.django_db
def test_purpose_backfill_sets_org_admin_for_null_rows():
    """Backfill function sets purpose='ORG_ADMIN' and invited_for_role='ORG_ADMIN'
    for rows that previously had NULL in those columns.

    We verify the logic of the backfill function by confirming it calls .update()
    with the correct values on a queryset filtered for purpose__isnull=True.
    Since the post-migration schema enforces NOT NULL, we test the function's
    query logic directly via mock.
    """
    mod = importlib.import_module("apps.accounts.migrations.0005_invitationtoken_purpose_backfill")

    # Build a fake apps registry that returns a mock InvitationToken model
    mock_qs = MagicMock()
    mock_manager = MagicMock()
    mock_manager.filter.return_value = mock_qs
    mock_token_model = MagicMock()
    mock_token_model.objects = mock_manager

    mock_apps = MagicMock()
    mock_apps.get_model.return_value = mock_token_model

    mod.backfill_purpose(mock_apps, None)

    # Assert the function fetched the right model
    mock_apps.get_model.assert_called_once_with("accounts", "InvitationToken")
    # Assert it filtered by purpose__isnull=True
    mock_manager.filter.assert_called_once_with(purpose__isnull=True)
    # Assert it updated with the correct values
    mock_qs.update.assert_called_once_with(
        purpose="ORG_ADMIN",
        invited_for_role="ORG_ADMIN",
    )


def test_purpose_field_is_not_null():
    """After migration 0005, InvitationToken.purpose must be NOT NULL."""
    field = InvitationToken._meta.get_field("purpose")
    assert field.null is False


def test_invited_for_role_field_is_not_null():
    """After migration 0005, InvitationToken.invited_for_role must be NOT NULL."""
    field = InvitationToken._meta.get_field("invited_for_role")
    assert field.null is False
