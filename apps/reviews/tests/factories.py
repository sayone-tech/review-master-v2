from __future__ import annotations

from typing import ClassVar

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag
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
    extracted_action_items: ClassVar[list] = []


class OrgCanonicalTagFactory(DjangoModelFactory):
    class Meta:
        model = OrgCanonicalTag

    organisation = factory.SubFactory(OrganisationFactory)
    label = factory.Sequence(lambda n: f"Canonical {n}")
    polarity_type = OrgCanonicalTag.PolarityType.MIXED
    review_count = 0


class ReviewTagFactory(DjangoModelFactory):
    class Meta:
        model = ReviewTag

    review = factory.SubFactory(ReviewFactory)
    label = factory.Faker("word")
    polarity = "positive"
    canonical_tag = None


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
