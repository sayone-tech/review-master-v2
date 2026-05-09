from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reply_templates.models import ReplyTemplate
from apps.reply_templates.tests.factories import ReplyTemplateFactory


@pytest.fixture
def org_and_admin(db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=admin)
    return org, admin, client


@pytest.fixture
def org_and_staff(db):
    org = OrganisationFactory()
    staff = UserFactory(role="STAFF_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=staff)
    return org, staff, client


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTemplateList:
    def test_org_admin_can_list(self, org_and_admin):
        org, _, client = org_and_admin
        ReplyTemplateFactory(organisation=org)
        resp = client.get("/api/v1/reply-templates/")
        assert resp.status_code == 200

    def test_staff_can_list(self, org_and_staff):
        org, _, client = org_and_staff
        ReplyTemplateFactory(organisation=org)
        resp = client.get("/api/v1/reply-templates/")
        assert resp.status_code == 200

    def test_list_scoped_to_org(self, org_and_admin):
        org, _, client = org_and_admin
        own = ReplyTemplateFactory(organisation=org)
        other_org = OrganisationFactory()
        other = ReplyTemplateFactory(organisation=other_org)
        resp = client.get("/api/v1/reply-templates/")
        ids = [r["id"] for r in resp.data["results"]]
        assert own.pk in ids
        assert other.pk not in ids

    def test_unauthenticated_cannot_list(self, db):
        client = APIClient()
        resp = client.get("/api/v1/reply-templates/")
        assert resp.status_code in (401, 403)

    def test_list_fixed_query_count(self, org_and_admin):
        org, _, client = org_and_admin
        ReplyTemplateFactory.create_batch(20, organisation=org)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/v1/reply-templates/")
        assert resp.status_code == 200
        assert len(ctx.captured_queries) <= 5


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTemplateCreate:
    def test_org_admin_can_create(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post(
            "/api/v1/reply-templates/",
            {"name": "Thank You", "content": "Thanks for visiting!"},
        )
        assert resp.status_code == 201
        assert resp.data["name"] == "Thank You"
        assert resp.data["content"] == "Thanks for visiting!"

    def test_staff_cannot_create(self, org_and_staff):
        _, _, client = org_and_staff
        resp = client.post(
            "/api/v1/reply-templates/",
            {"name": "Thank You", "content": "Thanks for visiting!"},
        )
        assert resp.status_code == 403

    def test_name_required(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/reply-templates/", {"content": "Some content"})
        assert resp.status_code == 400
        assert "name" in resp.data

    def test_content_required(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/reply-templates/", {"name": "My Template"})
        assert resp.status_code == 400
        assert "content" in resp.data

    def test_name_too_long(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post(
            "/api/v1/reply-templates/",
            {"name": "x" * 101, "content": "Some content"},
        )
        assert resp.status_code == 400

    def test_template_scoped_to_org(self, org_and_admin):
        org, _, client = org_and_admin
        resp = client.post(
            "/api/v1/reply-templates/",
            {"name": "T", "content": "C"},
        )
        assert resp.status_code == 201
        template = ReplyTemplate.objects.get(pk=resp.data["id"])
        assert template.organisation == org


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTemplateUpdate:
    def test_org_admin_can_update(self, org_and_admin):
        org, _, client = org_and_admin
        template = ReplyTemplateFactory(organisation=org, name="Old")
        resp = client.patch(f"/api/v1/reply-templates/{template.pk}/", {"name": "New"})
        assert resp.status_code == 200
        assert resp.data["name"] == "New"

    def test_staff_cannot_update(self, org_and_staff):
        org, _, client = org_and_staff
        template = ReplyTemplateFactory(organisation=org)
        resp = client.patch(f"/api/v1/reply-templates/{template.pk}/", {"name": "New"})
        assert resp.status_code == 403

    def test_cannot_update_other_org_template(self, org_and_admin):
        _, _, client = org_and_admin
        other_org = OrganisationFactory()
        template = ReplyTemplateFactory(organisation=other_org)
        resp = client.patch(f"/api/v1/reply-templates/{template.pk}/", {"name": "Hack"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTemplateDelete:
    def test_org_admin_can_delete(self, org_and_admin):
        org, _, client = org_and_admin
        template = ReplyTemplateFactory(organisation=org)
        resp = client.delete(f"/api/v1/reply-templates/{template.pk}/")
        assert resp.status_code == 204
        assert not ReplyTemplate.objects.filter(pk=template.pk).exists()

    def test_staff_cannot_delete(self, org_and_staff):
        org, _, client = org_and_staff
        template = ReplyTemplateFactory(organisation=org)
        resp = client.delete(f"/api/v1/reply-templates/{template.pk}/")
        assert resp.status_code == 403

    def test_cannot_delete_other_org_template(self, org_and_admin):
        _, _, client = org_and_admin
        other_org = OrganisationFactory()
        template = ReplyTemplateFactory(organisation=other_org)
        resp = client.delete(f"/api/v1/reply-templates/{template.pk}/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_template_list_page_blocks_staff_admin(db):
    org = OrganisationFactory()
    staff = UserFactory(role="STAFF_ADMIN", organisation=org)
    from django.test import Client as DjangoClient

    c = DjangoClient()
    c.force_login(staff)
    resp = c.get("/admin/org/reply-templates/")
    # org_admin_required redirects wrong-role users to login rather than 403
    assert resp.status_code == 302


@pytest.mark.django_db
def test_template_list_page_renders_for_org_admin(db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    from django.test import Client as DjangoClient

    c = DjangoClient()
    c.force_login(admin)
    resp = c.get("/admin/org/reply-templates/")
    assert resp.status_code == 200
    assert b"Reply Templates" in resp.content
