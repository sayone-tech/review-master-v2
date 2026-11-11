from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.integrations.openai.client import REPLY_MODERATION_MAX_RETRIES

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


def test_lapse_chunk_size_is_positive_int_defaulting_to_500():
    size = settings.REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE
    assert isinstance(size, int)
    assert size > 0
    assert size == 500


def test_reaper_batch_size_is_positive_int_defaulting_to_500():
    size = settings.REVIEWBEE_CREDIT_REAPER_BATCH_SIZE
    assert isinstance(size, int)
    assert size > 0
    assert size == 500


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


def _worst_case_reply_seconds(
    *,
    timeout: float,
    chat_retries: int,
    moderation_retries: int,
    backoff_allowance: float = 8.0,
) -> float:
    """Whole-request worst case for one generate-reply (D-15, research A7).

    Two moderation calls, each up to two app-level attempts of `timeout *
    (moderation_retries + 1)` plus the 1 s sleep, plus the chat call with its SDK
    retry and a backoff allowance per retry.
    """
    moderation = 2 * (2 * timeout * (moderation_retries + 1) + 1.0)
    chat = timeout * (chat_retries + 1) + backoff_allowance * chat_retries
    return moderation + chat


def _ttl_seconds() -> int:
    return settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES * 60


def test_reply_openai_defaults_are_thirty_seconds_and_one_retry():
    assert settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS == 30
    assert settings.REVIEWBEE_REPLY_OPENAI_MAX_RETRIES == 1


def test_generate_reply_throttle_stays_ten_per_minute():
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["generate_reply"] == "10/minute"


def test_ttl_covers_twice_the_chat_call_worst_case():
    timeout = settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS
    retries = settings.REVIEWBEE_REPLY_OPENAI_MAX_RETRIES
    assert _ttl_seconds() >= 2 * timeout * (retries + 1)


def test_whole_request_budget_fits_inside_reservation_ttl():
    worst = _worst_case_reply_seconds(
        timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS,
        chat_retries=settings.REVIEWBEE_REPLY_OPENAI_MAX_RETRIES,
        moderation_retries=REPLY_MODERATION_MAX_RETRIES,
    )
    assert worst == 190
    assert worst <= _ttl_seconds()


def test_budget_helper_flags_violation_when_timeout_is_sixty_seconds():
    worst = _worst_case_reply_seconds(timeout=60, chat_retries=1, moderation_retries=0)
    assert worst == 370
    assert worst > _ttl_seconds()


def test_budget_boundary_is_inclusive_when_worst_case_equals_ttl():
    worst = _worst_case_reply_seconds(
        timeout=48, chat_retries=1, moderation_retries=0, backoff_allowance=10.0
    )
    assert worst == 300
    assert worst <= _ttl_seconds()


def test_shop_credits_throttle_rate_is_120_per_minute():
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["shop_credits"] == "120/minute"
