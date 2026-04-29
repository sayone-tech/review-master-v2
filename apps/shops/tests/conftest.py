from __future__ import annotations

# Re-export shared fixtures so they auto-discover for any test in apps/shops/tests/.
# Tests in OTHER apps must explicitly import from apps.common.tests.fixtures.
from apps.common.tests.fixtures import (  # noqa: F401
    assert_query_ceiling,
    two_orgs_two_admins,
)
