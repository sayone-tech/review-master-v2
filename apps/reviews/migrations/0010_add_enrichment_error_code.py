from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0007_replied_by_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="enrichment_error_code",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
