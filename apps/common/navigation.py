"""Sidebar navigation definition, per role.

Single source of truth for the grouped sidebar menu (see
docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    label: str
    href: str
    icon: str
    badge_key: str | None = None


@dataclass(frozen=True)
class NavGroup:
    key: str
    label: str | None
    items: tuple[NavItem, ...]


_ORG_ADMIN = (
    NavGroup(
        "overview", None, (NavItem("Dashboard", "/admin/org/dashboard/", "layout-dashboard"),)
    ),
    NavGroup(
        "feedback",
        "Customer feedback",
        (
            NavItem("Reviews", "/admin/org/reviews/", "star", badge_key="reviews"),
            NavItem(
                "Action items",
                "/admin/org/action-items/",
                "clipboard-list",
                badge_key="action_items",
            ),
            NavItem("Reports", "/admin/org/reports/", "bar-chart-2"),
        ),
    ),
    NavGroup(
        "locations",
        "Locations",
        (
            NavItem("Shops", "/admin/org/shops/", "store"),
            NavItem("Regions", "/admin/org/regions/", "map-pin"),
        ),
    ),
    NavGroup(
        "workspace",
        "Workspace",
        (
            NavItem("Tags", "/admin/org/tags/", "tags"),
            NavItem("Reply templates", "/admin/org/reply-templates/", "file-text"),
            NavItem("Team", "/admin/org/team/", "users"),
            NavItem("Activity log", "/admin/org/activity-log/", "clock"),
        ),
    ),
)

_STAFF = (
    NavGroup(
        "feedback",
        "Customer feedback",
        (
            NavItem("Reviews", "/admin/org/reviews/", "star", badge_key="reviews"),
            NavItem(
                "Action items",
                "/admin/org/action-items/",
                "clipboard-list",
                badge_key="action_items",
            ),
            NavItem("Activity log", "/admin/org/activity-log/", "clock"),
        ),
    ),
)

_SUPERADMIN = (
    NavGroup(
        "platform",
        "Platform",
        (
            NavItem("Dashboard", "/", "layout-dashboard"),
            NavItem("Organisations", "/admin/organisations/", "building-2"),
        ),
    ),
    NavGroup(
        "ai-spend",
        "AI spend",
        (
            NavItem("AI cost", "/admin/ai-cost/", "zap"),
            NavItem("AI pricing", "/admin/ai-pricing/", "receipt"),
        ),
    ),
    NavGroup(
        "developer",
        "Developer",
        (
            NavItem("Django admin", "/django-admin/", "shield"),
            NavItem("API docs", "/api/v1/schema/scalar/", "file-code"),
        ),
    ),
)

_BY_ROLE = {
    "ORG_ADMIN": _ORG_ADMIN,
    "STAFF_ADMIN": _STAFF,
    "SUPERADMIN": _SUPERADMIN,
}


def nav_groups_for(*, role: str) -> tuple[NavGroup, ...]:
    """Return the ordered nav groups for a user role (empty for unknown roles)."""
    return _BY_ROLE.get(role, ())
