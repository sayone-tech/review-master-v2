import type { PriceRow } from "./types";

export function priceRow(over: Partial<PriceRow> = {}): PriceRow {
  return {
    id: 1,
    model: "gpt-4o-mini",
    input_token_price_per_1m: "0.15000000",
    output_token_price_per_1m: "0.60000000",
    cached_token_price_per_1m: "0.07500000",
    effective_from: "2026-01-05T00:00:00Z",
    effective_to: null,
    source: "manual",
    created_by: { id: 3, name: "Ada Admin" },
    status: "current",
    can_delete: false,
    ...over,
  };
}
