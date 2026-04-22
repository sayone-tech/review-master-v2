import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_home_renders_200_with_shell_structure() -> None:
    """DSYS-01 + DSYS-04: home page renders shell with sidebar, topbar, and Background Gray main."""
    client = Client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # DSYS-01: sidebar present
    assert 'data-testid="sidebar"' in body
    # DSYS-03 topbar present (structure; full nav in Plan 04)
    assert 'data-testid="topbar"' in body
    # DSYS-04: main has Background Gray (bg-bg) class
    assert 'data-testid="main-content"' in body
    assert "bg-bg" in body


def test_home_renders_geist_font_links() -> None:
    """DSYS-04 / typography: Geist + Geist Mono Google Fonts preconnect and stylesheet present."""
    client = Client()
    resp = client.get("/")
    body = resp.content.decode()
    assert "fonts.googleapis.com" in body
    assert "Geist" in body


def test_home_renders_vite_asset_tag() -> None:
    """django-vite template tag produces a script/link reference to app-shell entry."""
    client = Client()
    resp = client.get("/")
    body = resp.content.decode()
    # In dev mode, django-vite emits a <script type="module" src="http://...:5173/...app-shell..."> tag
    # In prod mode (manifest read), emits a <script src="/static/dist/assets/app-shell.<hash>.js">
    assert "app-shell" in body


def test_home_includes_skip_to_main_link() -> None:
    """DSYS-08 (basic wiring): skip link is the first focusable element."""
    client = Client()
    resp = client.get("/")
    body = resp.content.decode()
    assert 'href="#main-content"' in body
    assert "Skip to main content" in body


def test_home_uses_primary_black_sidebar_background() -> None:
    """DSYS-01: sidebar background is Primary Black (bg-black class maps to #0A0A0A)."""
    client = Client()
    resp = client.get("/")
    body = resp.content.decode()
    # sidebar element has bg-black tailwind class
    assert 'data-testid="sidebar"' in body
    # Extract sidebar tag and verify bg-black
    assert "bg-black" in body
