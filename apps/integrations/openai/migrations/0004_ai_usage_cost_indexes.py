# Phase 34: AI Cost Explorer indexes.
#
# ai_usage_log is written on every enrichment / reply call, so the index is built
# CONCURRENTLY on PostgreSQL (no SHARE lock blocking INSERTs). That needs a
# non-atomic migration. Other backends (the SQLite test database) have no
# CONCURRENTLY and fall back to a plain AddIndex.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import ProjectState


class AddIndexConcurrentlyOnPostgres(AddIndexConcurrently):
    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        else:
            migrations.AddIndex.database_forwards(
                self, app_label, schema_editor, from_state, to_state
            )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)
        else:
            migrations.AddIndex.database_backwards(
                self, app_label, schema_editor, from_state, to_state
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("openai", "0003_add_moderated_status_choice"),
    ]

    operations = [
        AddIndexConcurrentlyOnPostgres(
            model_name="aiusagelog",
            index=models.Index(
                fields=["organisation", "status", "created_at"],
                name="ai_usage_org_stat_cr_idx",
            ),
        ),
    ]
