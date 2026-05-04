"""Phase 12 — configure_langsmith helper tests."""

from __future__ import annotations

import os

import pytest
from django.test import override_settings

from apps.integrations.openai.tracing import configure_langsmith


@pytest.fixture(autouse=True)
def _reset_langsmith_env_after_test() -> None:  # type: ignore[return]
    """Restore LANGSMITH_TRACING=false after each test so other tests are unaffected."""
    yield
    os.environ["LANGSMITH_TRACING"] = "false"


@override_settings(LANGSMITH_ENABLED=False, LANGSMITH_API_KEY=None)
def test_disabled_sets_tracing_false() -> None:
    configure_langsmith()
    assert os.environ["LANGSMITH_TRACING"] == "false"


@override_settings(
    LANGSMITH_ENABLED=True,
    LANGSMITH_API_KEY="fake-key",
    LANGSMITH_PROJECT="test-project",
)
def test_enabled_sets_tracing_true_and_exports_key_project() -> None:
    configure_langsmith()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "fake-key"
    assert os.environ["LANGSMITH_PROJECT"] == "test-project"


@override_settings(LANGSMITH_ENABLED=True, LANGSMITH_API_KEY=None)
def test_enabled_with_no_api_key_still_sets_tracing_true_with_empty_string() -> None:
    """Defensive: if ENABLED=True but API_KEY is None, export empty string (not None)."""
    configure_langsmith()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == ""
