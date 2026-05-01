"""INFRA-02: django-celery-beat schema migration creates the periodic task tables."""

import pytest
from django.conf import settings
from django.db import connection


@pytest.mark.django_db
def test_periodictask_table_exists() -> None:
    tables = set(connection.introspection.table_names())
    assert "django_celery_beat_periodictask" in tables


@pytest.mark.django_db
def test_intervalschedule_table_exists() -> None:
    tables = set(connection.introspection.table_names())
    assert "django_celery_beat_intervalschedule" in tables


@pytest.mark.django_db
def test_crontabschedule_table_exists() -> None:
    tables = set(connection.introspection.table_names())
    assert "django_celery_beat_crontabschedule" in tables


@pytest.mark.django_db
def test_solarschedule_table_exists() -> None:
    tables = set(connection.introspection.table_names())
    assert "django_celery_beat_solarschedule" in tables


def test_database_scheduler_setting() -> None:
    assert settings.CELERY_BEAT_SCHEDULER == "django_celery_beat.schedulers:DatabaseScheduler"
