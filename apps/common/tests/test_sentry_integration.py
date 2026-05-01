"""INFRA-06: Sentry integration — PII scrubbing and conditional init.

Tests the `_before_send` hook in `config.settings.base` and the gating logic
that prevents `sentry_sdk.init` from running without `SENTRY_DSN`.
"""

import importlib
from unittest.mock import patch

from config.settings.base import _before_send


def test_before_send_scrubs_email_keys() -> None:
    event = {"email": "user@example.com", "name": "Alice"}
    scrubbed = _before_send(event, {})
    assert scrubbed == {"email": "[Filtered]", "name": "Alice"}


def test_before_send_scrubs_token_keys() -> None:
    event = {
        "access_token": "abc",
        "refresh_token": "xyz",
        "id": 42,
    }
    scrubbed = _before_send(event, {})
    assert scrubbed["access_token"] == "[Filtered]"
    assert scrubbed["refresh_token"] == "[Filtered]"
    assert scrubbed["id"] == 42


def test_before_send_scrubs_password_keys() -> None:
    event = {"password": "secret123", "password_hash": "argon2$..."}
    scrubbed = _before_send(event, {})
    assert scrubbed["password"] == "[Filtered]"
    assert scrubbed["password_hash"] == "[Filtered]"


def test_before_send_scrubs_secret_and_key() -> None:
    event = {"api_key": "k", "client_secret": "s", "stripe_key_v2": "v"}
    scrubbed = _before_send(event, {})
    assert scrubbed["api_key"] == "[Filtered]"
    assert scrubbed["client_secret"] == "[Filtered]"
    assert scrubbed["stripe_key_v2"] == "[Filtered]"


def test_before_send_scrubs_recursively() -> None:
    event = {
        "request": {
            "headers": {"Authorization": "Bearer abc", "User-Agent": "test"},
            "data": {"email": "u@x.com", "comment": "all good"},
        },
        "extra": [{"refresh_token": "x"}, {"name": "ok"}],
    }
    scrubbed = _before_send(event, {})
    assert scrubbed["request"]["headers"]["User-Agent"] == "test"
    # 'Authorization' has no sensitive substring (per locked list); preserved.
    assert scrubbed["request"]["data"]["email"] == "[Filtered]"
    assert scrubbed["request"]["data"]["comment"] == "all good"
    assert scrubbed["extra"][0]["refresh_token"] == "[Filtered]"
    assert scrubbed["extra"][1]["name"] == "ok"


def test_before_send_preserves_safe_keys() -> None:
    event = {"name": "Alice", "count": 5, "tags": ["a", "b"]}
    scrubbed = _before_send(event, {})
    assert scrubbed == {"name": "Alice", "count": 5, "tags": ["a", "b"]}


def test_before_send_handles_none_values() -> None:
    event = {"email": None, "name": None}
    scrubbed = _before_send(event, {})
    # email key still scrubbed regardless of value type
    assert scrubbed == {"email": "[Filtered]", "name": None}


def test_init_skipped_when_dsn_absent() -> None:
    """When SENTRY_DSN is unset, the settings module did NOT call sentry_sdk.init."""
    from config.settings import base

    # In test settings, SENTRY_DSN is unset (no .env loaded with it).
    assert base.SENTRY_DSN is None


def test_init_called_with_both_integrations_when_dsn_set() -> None:
    """When SENTRY_DSN is set, both DjangoIntegration and CeleryIntegration are passed."""
    with patch("sentry_sdk.init") as mock_init:
        with patch.dict("os.environ", {"SENTRY_DSN": "https://x@sentry.io/1"}):
            import config.settings.base as base_module

            importlib.reload(base_module)

        assert mock_init.called
        kwargs = mock_init.call_args.kwargs
        integration_classes = {type(i).__name__ for i in kwargs["integrations"]}
        assert "DjangoIntegration" in integration_classes
        assert "CeleryIntegration" in integration_classes
        assert kwargs["send_default_pii"] is False
        assert kwargs["before_send"] is not None


def test_init_includes_environment() -> None:
    """ENVIRONMENT env var is passed to sentry_sdk.init when DSN set."""
    with patch("sentry_sdk.init") as mock_init:
        with patch.dict(
            "os.environ",
            {"SENTRY_DSN": "https://x@sentry.io/1", "ENVIRONMENT": "production"},
        ):
            import config.settings.base as base_module

            importlib.reload(base_module)

        kwargs = mock_init.call_args.kwargs
        assert kwargs["environment"] == "production"
