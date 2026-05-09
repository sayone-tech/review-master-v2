from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.reply_templates.models import ReplyTemplate


class ReplyTemplateFactory(DjangoModelFactory):
    class Meta:
        model = ReplyTemplate

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    name = factory.Sequence(lambda n: f"Template {n}")
    content = factory.Sequence(
        lambda n: f"Thank you for your review #{n}. We appreciate your feedback."
    )
