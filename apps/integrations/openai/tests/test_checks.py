"""Phase 35 task 4 - deploy-time check that the configured model has a price."""

from __future__ import annotations

import pytest
from django.core.checks import Warning as CheckWarning
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.db.utils import OperationalError

from apps.integrations.openai import checks
from apps.integrations.openai.checks import check_configured_model_priced


@pytest.mark.django_db
def test_check_errors_when_configured_model_unpriced(settings):
    settings.OPENAI_MODEL = "gpt-unpriced"
    errors = check_configured_model_priced(None, databases=["default"])
    assert [e.id for e in errors] == ["openai.E001"]
    assert "gpt-unpriced" in errors[0].msg
    assert (
        errors[0].hint == "Add a price on /admin/ai-pricing/ or via Django admin before deploying."
    )


@pytest.mark.django_db
def test_check_passes_when_priced(settings):
    settings.OPENAI_MODEL = "gpt-4o-mini-2024-07-18"  # seeded by migration 0002
    assert check_configured_model_priced(None, databases=["default"]) == []


def test_check_skipped_without_databases(settings):
    settings.OPENAI_MODEL = "gpt-unpriced"
    assert check_configured_model_priced(None, databases=None) == []


@pytest.mark.django_db
def test_check_runs_via_call_command(settings):
    settings.OPENAI_MODEL = "gpt-unpriced"
    with pytest.raises(SystemCheckError, match=r"openai\.E001"):
        call_command("check", "--database", "default", "--fail-level", "ERROR")


@pytest.mark.django_db
def test_plain_check_does_not_touch_database(settings):
    """CI runs `check --deploy` without --database; an unpriced model must not fail it."""
    settings.OPENAI_MODEL = "gpt-unpriced"
    call_command("check")


@pytest.mark.django_db
def test_missing_table_yields_warning_not_error(settings, monkeypatch):
    def boom(*args, **kwargs):
        raise OperationalError("no such table: openai_ai_pricing")

    monkeypatch.setattr(checks.AiPricing.objects, "get_active", boom, raising=False)
    messages = check_configured_model_priced(None, databases=["default"])
    assert [m.id for m in messages] == ["openai.W001"]
    assert isinstance(messages[0], CheckWarning)
