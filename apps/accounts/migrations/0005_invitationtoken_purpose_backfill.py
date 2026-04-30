from __future__ import annotations

from typing import Any

from django.db import migrations, models


def backfill_purpose(apps: Any, schema_editor: Any) -> None:
    InvitationToken = apps.get_model("accounts", "InvitationToken")
    InvitationToken.objects.filter(purpose__isnull=True).update(
        purpose="ORG_ADMIN",
        invited_for_role="ORG_ADMIN",
    )


class Migration(migrations.Migration):

    dependencies = [("accounts", "0004_staffaccessscope")]

    operations = [
        migrations.RunPython(backfill_purpose, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invitationtoken",
            name="purpose",
            field=models.CharField(
                max_length=20,
                choices=[("ORG_ADMIN", "Org Admin Setup"), ("TEAM_MEMBER", "Team Member Invitation")],
                db_index=True,
            ),
        ),
        migrations.AlterField(
            model_name="invitationtoken",
            name="invited_for_role",
            field=models.CharField(
                max_length=20,
                choices=[("SUPERADMIN", "Superadmin"), ("ORG_ADMIN", "Org Admin"), ("STAFF_ADMIN", "Staff Admin")],
            ),
        ),
    ]
