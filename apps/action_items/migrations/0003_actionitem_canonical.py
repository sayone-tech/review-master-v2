# Generated for Phase 18 — Plan 18-01: ActionItem duplicate merge data foundation.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("action_items", "0002_actionitem_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="canonical",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="duplicates",
                to="action_items.actionitem",
            ),
        ),
    ]
