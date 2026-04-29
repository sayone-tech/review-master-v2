from __future__ import annotations


class LastManagerError(Exception):
    """Raised when removing or demoting the only active ORG_ADMIN of an org."""
