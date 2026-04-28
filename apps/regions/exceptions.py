from __future__ import annotations


class RegionHasShopsError(Exception):
    """Raised by delete_region() when the region has one or more shops assigned."""

    def __init__(self, shop_count: int) -> None:
        self.shop_count = shop_count
        super().__init__(f"Region has {shop_count} shop(s) assigned.")
