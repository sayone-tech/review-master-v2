"""Add the ``running`` choice to ``AiPricingSyncConfig.last_status`` (choices only; no DB change)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("openai", "0008_backfill_hand_entered_prices_manual")]

    operations = [
        migrations.AlterField(
            model_name="aipricingsyncconfig",
            name="last_status",
            field=models.CharField(
                choices=[
                    ("never", "Never run"),
                    ("running", "Running"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                ],
                default="never",
                max_length=10,
            ),
        ),
    ]
