from __future__ import annotations


class ShopAtLimitError(Exception):
    """Raised when create_shop would exceed organisation.number_of_stores."""


class PlaceIdLockedError(Exception):
    """Raised when update_shop is asked to change connection_method or place_id."""
