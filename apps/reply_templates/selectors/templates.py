from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.reply_templates.models import ReplyTemplate


def list_templates(*, organisation_id: int, search: str = "") -> QuerySet[ReplyTemplate]:
    qs = ReplyTemplate.objects.filter(organisation_id=organisation_id)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(content__icontains=search))
    return qs
