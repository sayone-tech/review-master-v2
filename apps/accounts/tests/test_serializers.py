"""Tests for apps.accounts.serializers — TeamMember serializers.

Tests TDD (red first) the three behaviours documented in the Plan 02 spec.
"""

from __future__ import annotations

import pytest

from apps.accounts.models import StaffAccessScope, User
from apps.accounts.serializers import (
    TeamMemberCreateSerializer,
    TeamMemberReadSerializer,
)
from apps.accounts.tests.factories import StaffAccessScopeFactory, UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory

pytestmark = pytest.mark.django_db


class TestTeamMemberReadSerializerPrefetch:
    """TEAM-01: serializer reads prefetched_scopes to_attr without extra queries."""

    def test_team_member_read_uses_prefetched_scopes(self, db) -> None:
        """Monkey-patch a fake instance with prefetched_scopes; no DB hit for scopes."""
        org = OrganisationFactory()
        user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
        region = RegionFactory(organisation=org)
        scope = StaffAccessScopeFactory(
            user=user,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=region,
        )

        # Simulate the to_attr=prefetched_scopes list that the selector attaches.
        user.prefetched_scopes = [scope]  # type: ignore[attr-defined]

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            data = TeamMemberReadSerializer(user).data

        # Should not issue an extra query for scopes — they come from prefetched_scopes.
        scope_queries = [q for q in ctx.captured_queries if "staffaccessscope" in q["sql"].lower()]
        assert len(scope_queries) == 0, (
            f"Expected 0 scope queries when prefetched_scopes is set, got {len(scope_queries)}"
        )
        assert len(data["access_scopes"]) == 1
        assert data["access_scopes"][0]["scope_type"] == StaffAccessScope.ScopeType.REGION

    def test_team_member_read_falls_back_when_no_prefetch(self, db) -> None:
        """Instance without prefetched_scopes attr — serializer falls back to DB query."""
        org = OrganisationFactory()
        user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
        region = RegionFactory(organisation=org)
        StaffAccessScopeFactory(
            user=user,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=region,
        )

        # No prefetched_scopes attribute — must use the DB fallback.
        assert not hasattr(user, "prefetched_scopes")

        data = TeamMemberReadSerializer(user).data
        assert len(data["access_scopes"]) == 1


class TestTeamMemberCreateSerializerValidation:
    """TEAM-01 / create validation: scope required for STAFF_ADMIN."""

    def test_team_member_create_validates_scopes_for_staff(self, db) -> None:
        """POST with role=STAFF_ADMIN and empty region_ids+shop_ids → ValidationError."""
        data = {
            "full_name": "Jane Staff",
            "email": "janestaff@example.com",
            "invited_for_role": "STAFF_ADMIN",
            "region_ids": [],
            "shop_ids": [],
        }
        serializer = TeamMemberCreateSerializer(data=data)
        assert not serializer.is_valid()
        error_text = str(serializer.errors)
        assert "region" in error_text.lower() or "store" in error_text.lower()

    def test_team_member_create_allows_org_admin_without_scopes(self, db) -> None:
        """ORG_ADMIN invite does not require scopes."""
        data = {
            "full_name": "Jane Manager",
            "email": "janemanager@example.com",
            "invited_for_role": "ORG_ADMIN",
            "region_ids": [],
            "shop_ids": [],
        }
        serializer = TeamMemberCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_email_uniqueness_validated(self, db) -> None:
        """Duplicate email returns a validation error."""
        existing = UserFactory(email="taken@example.com")
        data = {
            "full_name": "Dupe User",
            "email": existing.email,
            "invited_for_role": "ORG_ADMIN",
        }
        serializer = TeamMemberCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors


class TestTeamMemberUpdateSerializerEmailLocked:
    """TEAM-08: email field must NOT appear in TeamMemberUpdateSerializer."""

    def test_update_serializer_has_no_email_field(self) -> None:
        from apps.accounts.serializers import TeamMemberUpdateSerializer

        assert "email" not in TeamMemberUpdateSerializer().fields
