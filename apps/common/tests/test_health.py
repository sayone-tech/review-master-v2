import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_healthz_returns_200_ok() -> None:
    client = Client()
    resp = client.get("/healthz/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_returns_ready_when_deps_up() -> None:
    client = Client()
    resp = client.get("/readyz/")
    # In test settings, DB (SQLite in-memory) and Redis (locmem cache) both up
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
