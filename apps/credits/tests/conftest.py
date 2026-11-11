from __future__ import annotations

# Re-export shared fixtures so they auto-discover for any test in apps/credits/tests/.
from apps.common.tests.fixtures import (  # noqa: F401
    assert_query_ceiling,
    two_orgs_two_admins,
)
