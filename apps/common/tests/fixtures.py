from __future__ import annotations

from collections.abc import Callable

import pytest
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.fixture
def two_orgs_two_admins(db):
    """Two organisations, one ORG_ADMIN each -- for cross-tenant isolation tests.

    Returns a dict: {org_a, org_b, admin_a, admin_b} where admin_a.organisation == org_a
    and admin_b.organisation == org_b.
    """
    org_a = OrganisationFactory(name="Org A")
    org_b = OrganisationFactory(name="Org B")
    admin_a = UserFactory(
        role=User.Role.ORG_ADMIN,
        organisation=org_a,
        email="admin-a@example.com",
    )
    admin_b = UserFactory(
        role=User.Role.ORG_ADMIN,
        organisation=org_b,
        email="admin-b@example.com",
    )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
    }


@pytest.fixture
def assert_query_ceiling() -> Callable[[CaptureQueriesContext, int], None]:
    """Assert a CaptureQueriesContext recorded at most max_queries queries.

    Usage:
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def test_my_list(client, assert_query_ceiling):
            with CaptureQueriesContext(connection) as ctx:
                response = client.get("/api/v1/regions/")
            assert_query_ceiling(ctx, max_queries=5)
    """

    def _assert(ctx: CaptureQueriesContext, max_queries: int) -> None:
        count = len(ctx.captured_queries)
        assert count <= max_queries, (
            f"Query count {count} exceeds ceiling {max_queries}.\n"
            f"Queries:\n"
            + "\n".join(f"  [{i}] {q['sql'][:120]}" for i, q in enumerate(ctx.captured_queries))
        )

    return _assert
