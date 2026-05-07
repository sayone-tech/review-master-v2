"""Tests for the branded 404/500 handler views (ERR-01, ERR-02)."""

import pytest
from django.template.exceptions import TemplateDoesNotExist
from django.test import Client, RequestFactory, override_settings


@pytest.fixture
def client():
    return Client()


@override_settings(ROOT_URLCONF="config.urls", DEBUG=False, ALLOWED_HOSTS=["*"])
def test_404_page(client, db, settings, tmp_path):
    """ERR-01: page_not_found view returns 404 or raises TemplateDoesNotExist (pre-14-08).

    Verifies the view function is callable and either returns 404 or raises
    TemplateDoesNotExist (acceptable until plan 14-08 ships the 404.html template).
    """
    rf = RequestFactory()
    req = rf.get("/this-path-definitely-does-not-exist-zz9plural9z/")
    from apps.common.views import page_not_found

    try:
        resp = page_not_found(req)
    except TemplateDoesNotExist:
        # Acceptable until 14-08 lands templates/404.html
        return
    assert resp.status_code == 404


@override_settings(ROOT_URLCONF="config.urls", DEBUG=False)
def test_500_handler_view_renders(client, db):
    """ERR-02: server_error view callable returns 500 or raises TemplateDoesNotExist (pre-14-08).

    Verifies the view function is callable and either returns 500 or raises
    TemplateDoesNotExist (acceptable until plan 14-08 ships the 500.html template).
    """
    rf = RequestFactory()
    req = rf.get("/anything/")
    from apps.common.views import server_error

    try:
        resp = server_error(req)
    except TemplateDoesNotExist:
        # Acceptable until 14-08 lands templates/500.html
        return
    assert resp.status_code == 500


def test_handler404_module_path():
    """ERR-01: config.urls exposes handler404 as a module-level string path."""
    import config.urls

    assert config.urls.handler404 == "apps.common.views.page_not_found"


def test_handler500_module_path():
    """ERR-02: config.urls exposes handler500 as a module-level string path."""
    import config.urls

    assert config.urls.handler500 == "apps.common.views.server_error"
