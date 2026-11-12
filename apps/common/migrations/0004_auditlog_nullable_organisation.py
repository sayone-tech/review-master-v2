"""Make ``AuditLog.organisation`` nullable for platform-level events (Phase 35).

A plain ``AlterField`` on PostgreSQL drops the FK, drops NOT NULL and re-adds a *validated*
FK — an ACCESS EXCLUSIVE lock on ``common_audit_log`` held while every row is re-checked,
blocking audit writes on the enrichment / action-item / credits / review paths. On PostgreSQL
this migration therefore only runs ``DROP NOT NULL`` (metadata-only, guarded by a short
``lock_timeout``) and leaves the FK untouched; the model state is still the full
``AlterField``. Other backends (the SQLite test DB) use the normal ``AlterField`` path.

Reversal (``SET NOT NULL``) fails once platform rows (``organisation IS NULL``) exist — they
must be deleted or re-homed before rolling back.
"""

from typing import Any

import django.db.models.deletion
from django.db import migrations, models

def _field() -> models.ForeignKey[Any, Any]:
    return models.ForeignKey(
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.CASCADE,
        related_name="audit_logs",
        to="organisations.organisation",
    )


class _DropNotNullOnPostgres(migrations.AlterField):
    """``AlterField`` whose PostgreSQL DDL is just ``DROP/SET NOT NULL`` (FK untouched)."""

    def database_forwards(
        self, app_label: str, schema_editor: Any, from_state: Any, to_state: Any
    ) -> None:
        if schema_editor.connection.vendor != "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)
            return
        schema_editor.execute("SET LOCAL lock_timeout = '5s'")
        schema_editor.execute(
            "ALTER TABLE common_audit_log ALTER COLUMN organisation_id DROP NOT NULL"
        )

    def database_backwards(
        self, app_label: str, schema_editor: Any, from_state: Any, to_state: Any
    ) -> None:
        if schema_editor.connection.vendor != "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)
            return
        schema_editor.execute("SET LOCAL lock_timeout = '5s'")
        schema_editor.execute(
            "ALTER TABLE common_audit_log ALTER COLUMN organisation_id SET NOT NULL"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0003_periodic_tasks_seed_celery_metrics"),
        ("organisations", "0003_organisation_monthly_credit_allocation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(model_name="auditlog", name="organisation", field=_field()),
            ],
            database_operations=[
                _DropNotNullOnPostgres(model_name="auditlog", name="organisation", field=_field()),
            ],
        ),
    ]
