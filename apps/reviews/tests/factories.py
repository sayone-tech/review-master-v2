from __future__ import annotations

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import Review
from apps.shops.tests.factories import ShopFactory


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    organisation = factory.SubFactory(OrganisationFactory)
    shop = factory.LazyAttribute(lambda o: ShopFactory(organisation=o.organisation))
    google_review_id = factory.Sequence(lambda n: f"google-rev-{n}")
    google_account_id = "accounts/123"
    google_location_id = "accounts/123/locations/456"
    star_rating = 5
    reviewer_display_name = factory.Faker("name")
    reviewer_photo_url = ""
    reviewer_is_anonymous = False
    comment = factory.Faker("paragraph")
    review_create_time = factory.LazyFunction(timezone.now)
    review_update_time = factory.LazyFunction(timezone.now)
    reply_comment = ""
    is_replied = False
    enrichment_status = Review.EnrichmentStatus.PENDING
    sentiment = ""


class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    organisation = factory.SubFactory(OrganisationFactory)
    actor = None
    entity_type = "review"
    entity_id = factory.Sequence(lambda n: str(n))
    action = "reply_posted"
    before_data = None
    after_data = factory.LazyFunction(lambda: {"reply_text": "ok"})
