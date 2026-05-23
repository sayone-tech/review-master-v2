from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("openai", "0002_seed_aiprice_gpt4o_mini"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiusagelog",
            name="status",
            field=models.CharField(
                choices=[
                    ("SUCCESS", "Success"),
                    ("FAILED", "Failed"),
                    ("MODERATED", "Moderated"),
                ],
                max_length=10,
            ),
        ),
    ]
