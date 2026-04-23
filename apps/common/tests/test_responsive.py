import pytest
from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse


@pytest.fixture
def request_at_path(rf: RequestFactory):
    def _make(path: str):
        req = rf.get(path)
        req.user = None
        return req

    return _make


def test_is_active_route_tag_matches_prefix(rf: RequestFactory):
    req = rf.get("/organisations/42/")
    tpl = Template('{% load ui %}{% is_active_route "/organisations/" as active %}{{ active }}')
    out = tpl.render(Context({"request": req}))
    assert out.strip() == "True"


def test_is_active_route_tag_does_not_match_other_path(rf: RequestFactory):
    req = rf.get("/profile/")
    tpl = Template('{% load ui %}{% is_active_route "/organisations/" as active %}{{ active }}')
    out = tpl.render(Context({"request": req}))
    assert out.strip() == "False"


def test_logout_url_name_resolves_in_phase_1():
    """{% url 'logout' %} must resolve without NoReverseMatch.

    This prevents template render failures in sidebar.html and topbar.html
    before Phase 2 wires django.contrib.auth.urls. Stub redirects to '/'.
    """
    assert reverse("logout") == "/logout/"


@pytest.mark.django_db
def test_logout_post_returns_302_to_login(client):
    resp = client.post("/logout/")
    assert resp.status_code == 302
    assert resp["Location"] == "/login/"


@pytest.mark.django_db
def test_logout_get_returns_405(client):
    # Django 5+ LogoutView accepts POST only
    resp = client.get("/logout/")
    assert resp.status_code == 405


@pytest.mark.django_db
def test_shell_renders_responsive_sidebar_classes(client):
    resp = client.get("/")
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        html = resp.content.decode()
        # Sidebar responsive classes
        assert "md:w-sidebar-rail" in html or "lg:w-sidebar" in html
        # Mobile hamburger aria-label
        assert 'aria-label="Open navigation"' in html
        # Skip link
        assert 'href="#main-content"' in html


@pytest.mark.django_db
def test_topbar_has_avatar_dropdown_alpine_state(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="t@example.com",
        password="xxxxxxxxxx",
        full_name="Tee Oh",
        role="SUPERADMIN",
    )
    client.force_login(user)
    resp = client.get("/")
    html = resp.content.decode()
    assert 'x-data="{ open: false }"' in html
    assert '@click.outside="open = false"' in html
    assert 'aria-label="Open user menu"' in html


@pytest.mark.django_db
def test_sidebar_and_topbar_render_logout_url_without_noreversematch(client, django_user_model):
    """Regression test: rendering the shell must NOT raise NoReverseMatch
    for {% url 'logout' %} in sidebar.html or topbar.html."""
    user = django_user_model.objects.create_user(
        email="t2@example.com",
        password="xxxxxxxxxx",
        full_name="Tee Oh",
        role="SUPERADMIN",
    )
    client.force_login(user)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.content.decode()
    # Logout form action resolves to the stub URL
    assert 'action="/logout/"' in html
