/** Server payload of GET /api/v1/shops/{id}/credits/ (Plan 33-04 contract). */
export interface ShopCredits {
  shop_id: number;
  period: { year: number; month: number };
  period_label: string;
  renews_on: string;
  allocated: number;
  bonus: number;
  consumed: number;
  remaining: number;
  total: number;
  is_enabled: boolean;
}

export class ShopCreditsError extends Error {
  status: number;

  constructor(status: number) {
    super(`Shop credits request failed (${status})`);
    this.name = "ShopCreditsError";
    this.status = status;
  }
}

/** Fetch one shop's balance fresh from the server (the endpoint is no-store). */
export async function getShopCredits(shopId: number, signal?: AbortSignal): Promise<ShopCredits> {
  const resp = await fetch(`/api/v1/shops/${shopId}/credits/`, {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!resp.ok) throw new ShopCreditsError(resp.status);
  return (await resp.json()) as ShopCredits;
}
