from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organisations", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="organisation",
            name="allow_custom_sync_depth",
            field=models.BooleanField(default=False),
        ),
    ]
