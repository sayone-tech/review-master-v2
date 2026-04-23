from __future__ import annotations

import re
from typing import Any, ClassVar

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Per-IP rate limit on the login endpoint.

    10 POST attempts per 15 minutes per client IP, backed by Redis DB 1
    (the "throttle" cache alias — see CLAUDE.md §7.5).

    Overrides parse_rate to support multi-unit periods such as "10/15min"
    because DRF's built-in parser only reads the first character of the period
    and therefore cannot handle periods like "15min".
    """

    scope = "login"
    cache = caches["throttle"]

    # Regex: <num>/<count><unit>  e.g. "10/15min" or standard "10/m"
    _PERIOD_RE: ClassVar[re.Pattern[str]] = re.compile(r"^(\d+)(s|min|h|d)$", re.IGNORECASE)
    _UNIT_SECONDS: ClassVar[dict[str, int]] = {"s": 1, "min": 60, "h": 3600, "d": 86400}

    def parse_rate(self, rate: str | None) -> tuple[int | None, int | None]:
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        num_requests = int(num)

        m = self._PERIOD_RE.match(period)
        if m:
            count, unit = int(m.group(1)), m.group(2).lower()
            duration = count * self._UNIT_SECONDS[unit]
        else:
            # Fall back to DRF's single-character lookup for "s", "m", "h", "d"
            unit_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            duration = unit_map[period[0]]

        return (num_requests, duration)

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
