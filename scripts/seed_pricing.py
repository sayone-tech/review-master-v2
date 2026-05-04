"""Re-seed AiPricing after a data flush. Safe to run multiple times."""

from datetime import UTC, datetime
from decimal import Decimal

from apps.integrations.openai.models import AiPricing

MODEL = "gpt-4o-mini-2024-07-18"
EFFECTIVE_FROM = datetime(2024, 7, 18, tzinfo=UTC)

if AiPricing.objects.filter(model=MODEL, effective_to__isnull=True).exists():
    print(f"AiPricing row already exists for {MODEL} — no action needed.")  # noqa: T201
else:
    AiPricing.objects.create(
        model=MODEL,
        input_token_price_per_1m=Decimal("0.150000"),
        output_token_price_per_1m=Decimal("0.600000"),
        cached_token_price_per_1m=Decimal("0.075000"),
        effective_from=EFFECTIVE_FROM,
        effective_to=None,
    )
    print(f"Created AiPricing: {MODEL} — $0.15/$0.60/$0.075 per 1M tokens")  # noqa: T201
