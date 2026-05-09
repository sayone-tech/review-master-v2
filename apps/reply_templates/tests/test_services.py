from __future__ import annotations

import pytest

from apps.organisations.tests.factories import OrganisationFactory
from apps.reply_templates.models import ReplyTemplate
from apps.reply_templates.services.templates import (
    create_template,
    delete_template,
    update_template,
)
from apps.reply_templates.tests.factories import ReplyTemplateFactory


@pytest.mark.django_db
class TestCreateTemplate:
    def test_creates_template_with_correct_fields(self) -> None:
        org = OrganisationFactory()
        template = create_template(
            organisation=org,
            name="Welcome Response",
            content="Thank you for visiting us!",
        )
        assert template.pk is not None
        assert template.organisation == org
        assert template.name == "Welcome Response"
        assert template.content == "Thank you for visiting us!"

    def test_template_is_scoped_to_organisation(self) -> None:
        org1 = OrganisationFactory()
        org2 = OrganisationFactory()
        create_template(organisation=org1, name="T1", content="Content 1")
        create_template(organisation=org2, name="T2", content="Content 2")
        assert ReplyTemplate.objects.filter(organisation=org1).count() == 1
        assert ReplyTemplate.objects.filter(organisation=org2).count() == 1


@pytest.mark.django_db
class TestUpdateTemplate:
    def test_updates_name(self) -> None:
        template = ReplyTemplateFactory(name="Old Name")
        updated = update_template(template=template, name="New Name")
        assert updated.name == "New Name"

    def test_updates_content(self) -> None:
        template = ReplyTemplateFactory(content="Old content")
        updated = update_template(template=template, content="New content")
        assert updated.content == "New content"

    def test_no_op_when_nothing_changes(self) -> None:
        template = ReplyTemplateFactory(name="Same", content="Same content")
        updated = update_template(template=template, name="Same", content="Same content")
        assert updated.pk == template.pk

    def test_partial_update_only_name(self) -> None:
        template = ReplyTemplateFactory(name="Old", content="Keep this")
        updated = update_template(template=template, name="New")
        assert updated.name == "New"
        assert updated.content == "Keep this"


@pytest.mark.django_db
class TestDeleteTemplate:
    def test_deletes_template(self) -> None:
        template = ReplyTemplateFactory()
        pk = template.pk
        delete_template(template=template)
        assert not ReplyTemplate.objects.filter(pk=pk).exists()
