from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.integrations.openai.models import AiPricing, AiUsageLog
from apps.organisations.tests.factories import OrganisationFactory


class AiPricingFactory(DjangoModelFactory):
    class Meta:
        model = AiPricing

    model = "test-model"
    input_token_price_per_1m = Decimal("0.150000")
    output_token_price_per_1m = Decimal("0.600000")
    cached_token_price_per_1m = Decimal("0.075000")
    effective_from = factory.LazyFunction(lambda: datetime(2025, 1, 1, tzinfo=UTC))
    effective_to = None


class AiUsageLogFactory(DjangoModelFactory):
    class Meta:
        model = AiUsageLog

    organisation = factory.SubFactory(OrganisationFactory)
    review = None
    request_type = "enrichment"
    model = "gpt-4o-mini-2024-07-18"
    prompt_tokens = 500
    completion_tokens = 200
    cached_tokens = 0
    total_tokens = 700
    estimated_cost_usd = Decimal("0.000195")
    latency_ms = 1234
    langsmith_trace_id = "trace-abc-123"
    status = AiUsageLog.Status.SUCCESS
