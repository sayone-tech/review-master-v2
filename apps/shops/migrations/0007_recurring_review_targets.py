from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0006_add_review_target"),
    ]

    operations = [
        # 1. Wipe all existing per-period rows (incompatible with recurring design)
        migrations.RunSQL(
            "DELETE FROM shops_reviewtarget;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Drop old three-field unique constraint
        migrations.RemoveConstraint(
            model_name="reviewtarget",
            name="target_unique_per_shop_period",
        ),
        # 3. Drop old index
        migrations.RemoveIndex(
            model_name="reviewtarget",
            name="target_org_shop_period_idx",
        ),
        # 4. Drop period_start column
        migrations.RemoveField(
            model_name="reviewtarget",
            name="period_start",
        ),
        # 5. Add new two-field unique constraint
        migrations.AddConstraint(
            model_name="reviewtarget",
            constraint=models.UniqueConstraint(
                fields=["shop", "period_type"],
                name="target_unique_per_shop_period_type",
            ),
        ),
        # 6. Add new index (without period_start)
        migrations.AddIndex(
            model_name="reviewtarget",
            index=models.Index(
                fields=["organisation", "shop", "period_type"],
                name="tgt_org_shop_period_idx",
            ),
        ),
        # 7. Update ordering (remove period_start from ordering)
        migrations.AlterModelOptions(
            name="reviewtarget",
            options={
                "db_table": "shops_reviewtarget",
                "ordering": ["period_type"],
            },
        ),
    ]
