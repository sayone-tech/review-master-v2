from __future__ import annotations

from django.db import transaction

from apps.organisations.models import Organisation
from apps.reply_templates.models import ReplyTemplate


@transaction.atomic
def create_template(*, organisation: Organisation, name: str, content: str) -> ReplyTemplate:
    return ReplyTemplate.objects.create(
        organisation=organisation,
        name=name,
        content=content,
    )


@transaction.atomic
def update_template(
    *,
    template: ReplyTemplate,
    name: str | None = None,
    content: str | None = None,
) -> ReplyTemplate:
    changed: list[str] = []
    if name is not None and template.name != name:
        template.name = name
        changed.append("name")
    if content is not None and template.content != content:
        template.content = content
        changed.append("content")
    if changed:
        changed.append("updated_at")
        template.save(update_fields=changed)
    return template


def delete_template(*, template: ReplyTemplate) -> None:
    template.delete()
