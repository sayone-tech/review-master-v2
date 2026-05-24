from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0007_recurring_review_targets"),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="sync_depth",
            field=models.CharField(
                choices=[
                    ("ONE_YEAR", "Last 1 year"),
                    ("TWO_YEARS", "Last 2 years"),
                    ("ALL_TIME", "All time"),
                ],
                default="TWO_YEARS",
                max_length=10,
            ),
        ),
    ]
