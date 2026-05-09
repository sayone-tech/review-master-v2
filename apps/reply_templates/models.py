from __future__ import annotations

from typing import ClassVar

from django.db import models

from apps.common.models import TimeStampedModel


class ReplyTemplate(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="reply_templates",
    )
    name = models.CharField(max_length=100)
    content = models.TextField()

    class Meta:
        db_table = "reply_templates_replytemplate"
        ordering: ClassVar[list[str]] = ["created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation"],
                name="replytemplate_org_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name
