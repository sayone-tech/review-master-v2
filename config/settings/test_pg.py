"""Test settings against real PostgreSQL.

Used only by the ``backend-pg`` CI job and ``make test-pg`` (CQA-01): SQLite
serialises writers and hides the races the ``pg_concurrency`` tests exist to catch.
"""

from .test import *

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://app:app@localhost:5432/reviewmaster")
}
