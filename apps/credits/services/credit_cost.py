"""Credit pricing for a review: the single authoritative price function.

This is the ONLY place a review's credit cost is computed. The tier table lives in
``settings.REVIEWBEE_CREDIT_TIERS`` and is read here and nowhere else (a settings test
enforces that). The UI never recomputes the price; it shows the server value, so the
price shown always equals the price charged.

Callers pass the trimmed-at-source ``Review.comment`` (Phase 30). Review text is PII, so
nothing in this module logs it.

Length semantics (documented behaviour, not bugs):

- Length is ``len(text.strip())`` measured in Python code points, not grapheme clusters.
- A single-code-point emoji counts as 1.
- ZWJ sequences (e.g. a family emoji, 5 code points) and flags (2 regional indicators)
  count per code point.
- A comment made only of a zero-width space (U+200B) costs 1, because ``str.strip()``
  does not treat it as whitespace.

A cost of ``0`` means "not chargeable" (None, empty or whitespace-only input).
"""

from __future__ import annotations

from django.conf import settings


def credit_cost(text: str | None) -> int:
    """Return the credit cost (0 when not chargeable, else 1/2/3 with default tiers)."""
    length = len((text or "").strip())
    if length == 0:
        return 0
    tiers = settings.REVIEWBEE_CREDIT_TIERS
    for max_len, cost in tiers:
        if max_len is None or length <= max_len:
            return int(cost)
    # Malformed config (no open top tier): fall back to the most expensive tier.
    return int(tiers[-1][1])
