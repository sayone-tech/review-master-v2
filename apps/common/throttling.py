from __future__ import annotations

from typing import Any, ClassVar

from django.core.exceptions import ImproperlyConfigured
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class InviteScopedThrottle(ScopedRateThrottle):
    scope = "invite"


class GoogleSyncScopedThrottle(ScopedRateThrottle):
    scope = "google_sync"


class MultiplierRateThrottle(SimpleRateThrottle):
    """Per-user throttle whose rate may carry a period multiplier: ``"1/15m"`` = 1 per 900 s."""

    _PERIODS: ClassVar[dict[str, int]] = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    def parse_rate(self, rate: str | None) -> tuple[int | None, int | None]:
        if rate is None:
            return (None, None)
        try:
            num, period = rate.split("/")
            digits = "".join(ch for ch in period if ch.isdigit())
            unit = period[len(digits) :][:1]
            return (int(num), int(digits or 1) * self._PERIODS[unit])
        except (ValueError, KeyError) as exc:
            raise ImproperlyConfigured(
                f"Invalid throttle rate {rate!r} for scope {self.scope!r}: "
                'expected "<count>/<n><s|m|h|d>", e.g. "1/15m".'
            ) from exc

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        if not (request.user and request.user.is_authenticated):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class SyncTriggerThrottle(MultiplierRateThrottle):
    scope = "superadmin_ai_pricing_sync_trigger"
