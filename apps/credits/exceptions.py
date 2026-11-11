"""Ledger exceptions (D-05, D-06)."""

from __future__ import annotations


class AppendOnlyViolation(Exception):  # noqa: N818
    """Raised on any attempt to rewrite or remove a CreditTransaction row (D-05)."""


class InvalidStatusTransition(Exception):  # noqa: N818
    """Raised when a ledger status change is not RESERVED -> COMMITTED/REFUNDED, or loses the CAS (D-06)."""
