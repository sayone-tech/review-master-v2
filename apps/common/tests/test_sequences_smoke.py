"""django-sequences Django 6 compatibility smoke test (ROADMAP Phase 6 note).

RESEARCH confirms HIGH compatibility, but this regression test runs once per
session to fail fast if a future Django patch breaks the package. The
SequenceCounter fallback in apps/common/models.py is ready as insurance --
see apps/regions/services/sequences.py (Phase 7) for the activation path.
"""

from __future__ import annotations

import pytest
from django.db import transaction

pytestmark = pytest.mark.django_db


def test_django_sequences_get_next_value_works_against_test_db() -> None:
    """Smoke test: get_next_value() must return a positive integer."""
    from sequences import get_next_value

    with transaction.atomic():
        first = get_next_value("phase6_smoke_test")
    with transaction.atomic():
        second = get_next_value("phase6_smoke_test")
    assert isinstance(first, int)
    assert first >= 1
    assert isinstance(second, int)
    assert second == first + 1


def test_sequence_counter_fallback_model_is_available() -> None:
    """If django-sequences ever fails, this fallback model is ready to use."""
    from apps.common.models import SequenceCounter

    counter, _ = SequenceCounter.objects.get_or_create(
        name="fallback_smoke_test", defaults={"next_value": 1}
    )
    assert counter.name == "fallback_smoke_test"
    assert counter.next_value >= 1
