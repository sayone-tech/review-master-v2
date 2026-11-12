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
    assert errors[0].hint == "Add a price on /admin/ai-pricing/ before deploying."


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
        call_command("check", "--deploy", "--database", "default", "--fail-level", "ERROR")


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


@pytest.mark.django_db
def test_check_passes_when_configured_model_has_overlapping_windows(settings):
    from datetime import timedelta

    from django.utils import timezone

    from apps.integrations.openai.models import AiPricing
    from apps.integrations.openai.tests.factories import AiPricingFactory

    AiPricing.objects.filter(model="overlap-m").delete()
    settings.OPENAI_MODEL = "overlap-m"
    now = timezone.now()
    AiPricingFactory(
        model="overlap-m",
        effective_from=now - timedelta(days=10),
        effective_to=now + timedelta(days=1),
    )
    AiPricingFactory(model="overlap-m", effective_from=now - timedelta(days=2), effective_to=None)
    assert check_configured_model_priced(None, databases=["default"]) == []


@pytest.mark.django_db
def test_check_not_run_without_deploy_flag(settings):
    """migrate/runserver run database checks without deployment checks: must not block them."""
    from django.core.checks import run_checks

    settings.OPENAI_MODEL = "gpt-unpriced"
    ids = [m.id for m in run_checks(databases=["default"])]
    assert "openai.E001" not in ids
    call_command("check", "--database", "default", "--fail-level", "ERROR")


@pytest.mark.django_db
def test_migrate_plan_not_blocked_when_unpriced(settings):
    settings.OPENAI_MODEL = "gpt-unpriced"
    call_command("migrate", "--plan", skip_checks=False)


@pytest.mark.django_db
def test_deploy_check_with_database_reports_error(settings):
    from django.core.checks import run_checks

    settings.OPENAI_MODEL = "gpt-unpriced"
    ids = [m.id for m in run_checks(databases=["default"], include_deployment_checks=True)]
    assert "openai.E001" in ids
