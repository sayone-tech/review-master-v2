"""Ledger exceptions (D-05, D-06)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.credits.selectors.balances import CreditBalanceView
    from apps.credits.services.periods import Period


class AppendOnlyViolation(Exception):  # noqa: N818
    """Raised on any attempt to rewrite or remove a CreditTransaction row (D-05)."""


class InvalidStatusTransition(Exception):  # noqa: N818
    """Raised when a ledger status change is not RESERVED -> COMMITTED/REFUNDED, or loses the CAS (D-06)."""


class InsufficientCreditsError(Exception):
    """Raised when a shop cannot afford a reservation (D-08).

    ``reason`` is ``"not_enabled"`` (allocation + bonus == 0) or ``"exhausted"``
    (enabled, but ``remaining < required``).
    """

    def __init__(self, *, reason: str, required: int, remaining: int) -> None:
        super().__init__(
            f"insufficient credits: {reason} required={required} remaining={remaining}"
        )
        self.reason = reason
        self.required = required
        self.remaining = remaining


class GenerationInProgressError(Exception):
    """Raised when the review already has an unsettled (RESERVED) reservation (D-12)."""

    def __init__(self, *, review_id: int) -> None:
        super().__init__(f"generation already in progress for review {review_id}")
        self.review_id = review_id


class PeriodMismatchError(Exception):
    """Raised when a bonus request echoes a period other than the current UTC month (D-12).

    Carries the current period and the shop's fresh (possibly virtual) balance so the caller
    can repaint without a second round trip. Nothing is written on this path.
    """

    def __init__(self, *, current: Period, balance: CreditBalanceView) -> None:
        super().__init__(f"period mismatch: current={current.year}-{current.month:02d}")
        self.current = current
        self.balance = balance


class ShopNotAvailableError(Exception):
    """Raised when a shop is unknown, inactive, or belongs to a DELETED organisation (D-19)."""

    def __init__(self, *, shop_id: int) -> None:
        super().__init__(f"shop {shop_id} is not available for credit allocation")
        self.shop_id = shop_id
