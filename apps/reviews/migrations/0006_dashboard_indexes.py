from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0005_periodic_tasks_seed_retry_failed_enrichments"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["organisation", "review_create_time", "sentiment"],
                name="review_org_time_sent_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["shop", "review_create_time"],
                name="review_shop_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["organisation", "review_create_time", "enrichment_status"],
                name="review_org_time_status_idx",
            ),
        ),
    ]
