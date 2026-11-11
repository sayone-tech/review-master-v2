import os

import django
import pytest
from django.conf import settings  # noqa: F401


def pytest_configure(config: object) -> None:
    django.setup()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip ``pg_concurrency`` tests off PostgreSQL; hard-fail when PG is required.

    ``connection.vendor`` is a class attribute, so no DB connection opens at collection.
    ``REQUIRE_PG`` (set by the backend-pg CI job) turns a non-PostgreSQL run into exit
    status 3 so a misconfigured job can never go green with zero tests run.
    """
    from django.db import connection

    if connection.vendor == "postgresql":
        return
    if os.environ.get("REQUIRE_PG"):
        pytest.exit("REQUIRE_PG is set but the test database is not PostgreSQL", returncode=3)
    skip = pytest.mark.skip(reason="pg_concurrency requires PostgreSQL (use `make test-pg`)")
    for item in items:
        if "pg_concurrency" in item.keywords:
            item.add_marker(skip)
