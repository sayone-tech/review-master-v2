import re

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.navigation import nav_groups_for
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def _labels(role: str) -> list[tuple[str | None, list[str]]]:
    return [(g.label, [i.label for i in g.items]) for g in nav_groups_for(role=role)]


def _client_for(role: str) -> Client:
    org = None if role == User.Role.SUPERADMIN else OrganisationFactory()
    user = UserFactory(role=role, organisation=org)
    client = Client()
    client.force_login(user)
    return client


def test_org_admin_groups_and_items_in_order() -> None:
    assert _labels("ORG_ADMIN") == [
        (None, ["Dashboard"]),
        ("Customer feedback", ["Reviews", "Action items", "Reports"]),
        ("Locations", ["Shops", "Regions"]),
        ("Workspace", ["Tags", "Reply templates", "Team", "Activity log"]),
    ]
    assert [g.key for g in nav_groups_for(role="ORG_ADMIN")] == [
        "overview",
        "feedback",
        "locations",
        "workspace",
    ]


def test_staff_sees_only_reviews_action_items_activity_log() -> None:
    assert _labels("STAFF_ADMIN") == [
        ("Customer feedback", ["Reviews", "Action items", "Activity log"]),
    ]


def test_superadmin_groups() -> None:
    groups = nav_groups_for(role="SUPERADMIN")
    assert [g.key for g in groups] == ["platform", "ai-spend", "developer"]
    assert _labels("SUPERADMIN") == [
        ("Platform", ["Dashboard", "Organisations"]),
        ("AI spend", ["AI cost", "AI pricing"]),
        ("Developer", ["Django admin", "API docs"]),
    ]
    hrefs = [i.href for g in groups for i in g.items]
    assert hrefs == [
        "/",
        "/admin/organisations/",
        "/admin/ai-cost/",
        "/admin/ai-pricing/",
        "/django-admin/",
        "/api/v1/schema/scalar/",
    ]


def test_badge_keys_only_on_reviews_and_action_items() -> None:
    keyed = {
        i.label: i.badge_key
        for g in nav_groups_for(role="ORG_ADMIN")
        for i in g.items
        if i.badge_key
    }
    assert keyed == {"Reviews": "reviews", "Action items": "action_items"}


def test_unknown_role_has_no_groups() -> None:
    assert nav_groups_for(role="NOPE") == ()


def test_rendered_org_admin_sidebar_has_badge_slots_meter_and_summary_url() -> None:
    html = _client_for("ORG_ADMIN").get("/admin/org/reviews/").content.decode()
    assert "data-nav-summary-url" in html
    assert 'data-nav-badge="reviews"' in html
    assert 'data-nav-badge="action_items"' in html
    assert "data-nav-credits" in html
    assert "data-nav-credits-text" in html
    assert "data-nav-credits-bar" in html
    assert 'data-nav-group="feedback"' in html
    assert 'aria-controls="nav-group-feedback"' in html
    assert 'id="nav-group-feedback"' in html
    assert "data-nav-group-toggle" in html


def test_rendered_superadmin_sidebar_has_no_badges_meter_or_summary_url() -> None:
    html = _client_for("SUPERADMIN").get("/", follow=True).content.decode()
    assert 'data-testid="sidebar"' in html
    assert "data-nav-summary-url" not in html
    assert "data-nav-badge" not in html
    assert "data-nav-credits" not in html
    assert "Platform" in html


def test_staff_page_never_renders_org_admin_only_links() -> None:
    html = _client_for("STAFF_ADMIN").get("/admin/org/reviews/").content.decode()
    for href in (
        "/admin/org/shops/",
        "/admin/org/team/",
        "/admin/org/tags/",
        "/admin/org/regions/",
        "/admin/org/reports/",
        "/admin/org/reply-templates/",
        "/admin/org/dashboard/",
    ):
        assert f'href="{href}"' not in html
    assert 'href="/admin/org/reviews/"' in html
    assert "data-nav-summary-url" in html


def test_active_item_rendered_as_yellow_pill_with_aria_current() -> None:
    html = _client_for("ORG_ADMIN").get("/admin/org/reviews/").content.decode()
    match = re.search(r'<a\s[^>]*href="/admin/org/reviews/"[^>]*>', html)
    assert match
    tag = match.group(0)
    assert 'aria-current="page"' in tag
    assert "bg-yellow" in tag
    assert "text-black" in tag
    other = re.search(r'<a\s[^>]*href="/admin/org/action-items/"[^>]*>', html)
    assert other
    assert "aria-current" not in other.group(0)
    assert "bg-yellow" not in other.group(0)


def test_shell_keeps_main_content_contract_and_black_frame() -> None:
    html = _client_for("ORG_ADMIN").get("/admin/org/reviews/").content.decode()
    assert 'id="main-content"' in html
    assert "data-page-title" in html
    assert 'id="topbar-breadcrumb"' in html
    assert 'id="topbar-bell-root"' in html
    assert 'id="notif-bell-root"' in html
    assert 'id="main-sidebar"' in html
    assert 'id="main-topbar"' in html
    assert "data-turbo-permanent" in html
    assert "rounded-[14px]" in html


def _classes(tag: str) -> list[str]:
    match = re.search(r'class="([^"]*)"', tag)
    assert match
    return match.group(1).split()


def test_group_toggle_and_badge_have_base_classes_for_mobile_drawer() -> None:
    html = _client_for("ORG_ADMIN").get("/admin/org/reviews/").content.decode()
    toggle = re.search(r"<button[^>]*data-nav-group-toggle[^>]*>", html)
    assert toggle
    assert "flex" in _classes(toggle.group(0))
    badge = re.search(r'<span\s[^>]*data-nav-badge="reviews"[^>]*>', html)
    assert badge
    classes = _classes(badge.group(0))
    for base in ("rounded-full", "px-1.5", "text-[11px]", "min-w-[20px]", "text-center"):
        assert base in classes
    # Active item (Reviews) uses the black pill with yellow text below md.
    assert "bg-black" in classes
    assert "text-yellow" in classes
    inactive = re.search(r'<span\s[^>]*data-nav-badge="action_items"[^>]*>', html)
    assert inactive
    assert "bg-[#27272A]" in _classes(inactive.group(0))
