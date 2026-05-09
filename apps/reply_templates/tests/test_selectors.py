from __future__ import annotations

import pytest

from apps.organisations.tests.factories import OrganisationFactory
from apps.reply_templates.selectors.templates import list_templates
from apps.reply_templates.tests.factories import ReplyTemplateFactory


@pytest.mark.django_db
class TestListTemplates:
    def test_returns_templates_for_org(self) -> None:
        org = OrganisationFactory()
        t1 = ReplyTemplateFactory(organisation=org)
        t2 = ReplyTemplateFactory(organisation=org)
        result = list(list_templates(organisation_id=org.pk))
        assert t1 in result
        assert t2 in result

    def test_excludes_other_org_templates(self) -> None:
        org1 = OrganisationFactory()
        org2 = OrganisationFactory()
        t1 = ReplyTemplateFactory(organisation=org1)
        t2 = ReplyTemplateFactory(organisation=org2)
        result = list(list_templates(organisation_id=org1.pk))
        assert t1 in result
        assert t2 not in result

    def test_search_by_name(self) -> None:
        org = OrganisationFactory()
        match = ReplyTemplateFactory(organisation=org, name="Welcome Response")
        no_match = ReplyTemplateFactory(organisation=org, name="Apology Note")
        result = list(list_templates(organisation_id=org.pk, search="welcome"))
        assert match in result
        assert no_match not in result

    def test_search_by_content(self) -> None:
        org = OrganisationFactory()
        match = ReplyTemplateFactory(organisation=org, content="Thank you for your patience")
        no_match = ReplyTemplateFactory(organisation=org, content="We appreciate your feedback")
        result = list(list_templates(organisation_id=org.pk, search="patience"))
        assert match in result
        assert no_match not in result

    def test_empty_search_returns_all(self) -> None:
        org = OrganisationFactory()
        ReplyTemplateFactory.create_batch(3, organisation=org)
        result = list(list_templates(organisation_id=org.pk, search=""))
        assert len(result) == 3

    def test_ordered_by_created_at(self) -> None:
        org = OrganisationFactory()
        t1 = ReplyTemplateFactory(organisation=org)
        t2 = ReplyTemplateFactory(organisation=org)
        result = list(list_templates(organisation_id=org.pk))
        assert result.index(t1) < result.index(t2)
