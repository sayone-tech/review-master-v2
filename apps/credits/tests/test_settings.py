from __future__ import annotations

from pathlib import Path

from django.conf import settings

TIERS_NAME = "REVIEWBEE_CREDIT_TIERS"
ALLOWED_REFERENCERS = {
    "apps/credits/services/credit_cost.py",
    "config/settings/base.py",
}


def test_tiers_end_with_open_top_tier():
    assert settings.REVIEWBEE_CREDIT_TIERS[-1][0] is None


def test_bounded_tiers_have_positive_ascending_max_len():
    bounded = [max_len for max_len, _ in settings.REVIEWBEE_CREDIT_TIERS[:-1]]
    assert bounded, "at least one bounded tier is expected"
    assert all(isinstance(m, int) and m > 0 for m in bounded)
    assert bounded == sorted(set(bounded))


def test_tier_costs_are_positive_ints():
    assert all(isinstance(cost, int) and cost > 0 for _, cost in settings.REVIEWBEE_CREDIT_TIERS)


def test_reservation_ttl_is_five_minutes():
    assert settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES == 5


def test_support_email_is_non_empty_address():
    assert isinstance(settings.REVIEWBEE_SUPPORT_EMAIL, str)
    assert "@" in settings.REVIEWBEE_SUPPORT_EMAIL


def test_only_credit_cost_and_base_settings_reference_tiers_setting():
    root = Path(__file__).resolve().parents[3]
    found: set[str] = set()
    for sub in ("apps", "config"):
        for path in (root / sub).rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if "/tests/" in f"/{rel}" or "/migrations/" in f"/{rel}":
                continue
            if TIERS_NAME in path.read_text(encoding="utf-8"):
                found.add(rel)
    assert found == ALLOWED_REFERENCERS
