import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organisations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReplyTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("content", models.TextField()),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reply_templates",
                        to="organisations.organisation",
                    ),
                ),
            ],
            options={
                "db_table": "reply_templates_replytemplate",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(
                        fields=["organisation"],
                        name="replytemplate_org_idx",
                    )
                ],
            },
        ),
    ]
