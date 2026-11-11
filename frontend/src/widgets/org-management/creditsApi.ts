import { getCsrfToken } from "./api";

export interface CreditPeriod {
  year: number;
  month: number;
}

export interface CreditShopRow {
  id: number;
  name: string;
  allocated: number;
  bonus: number;
  consumed: number;
  remaining: number;
  is_materialized: boolean;
}

export interface CreditShopListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  period: CreditPeriod;
  allocation_per_shop: number;
  results: CreditShopRow[];
}

export interface BonusPayload {
  amount: number;
  reason?: string;
  period_year: number;
  period_month: number;
}

export interface BonusResult {
  shop_id: number;
  period: CreditPeriod;
  allocated: number;
  bonus: number;
  consumed: number;
  remaining: number;
  transaction_id: number;
}

export interface CreditBalanceSnapshot {
  shop_id: number;
  allocated: number;
  bonus: number;
  consumed: number;
  remaining: number;
}

export interface PeriodMismatchBody {
  code: "period_mismatch";
  detail: string;
  period: CreditPeriod;
  balance: CreditBalanceSnapshot;
}

/** Keeps the raw parsed JSON body (null when the body is not JSON) so callers can
 * branch on status and on the 409 / 400 body shapes. Not routed through api.ts
 * handle(), which would store any JSON error body as field errors. */
export class CreditsApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

export function isPeriodMismatch(
  err: unknown,
): err is CreditsApiError & { body: PeriodMismatchBody } {
  if (!(err instanceof CreditsApiError) || err.status !== 409) return false;
  const body = err.body as { code?: unknown } | null;
  return !!body && typeof body === "object" && body.code === "period_mismatch";
}

async function parseBody(resp: Response): Promise<unknown> {
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

export async function listCreditShops(
  orgId: number,
  params: { search: string; page: number },
  signal?: AbortSignal,
): Promise<CreditShopListResponse> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page));
  const search = params.search.trim();
  if (search) qs.set("search", search);
  const resp = await fetch(
    `/api/v1/superadmin/organisations/${orgId}/credits/shops/?${qs.toString()}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
      signal,
    },
  );
  if (!resp.ok) throw new CreditsApiError(resp.status, await parseBody(resp));
  return (await resp.json()) as CreditShopListResponse;
}

export async function allocateBonus(
  shopId: number,
  payload: BonusPayload,
): Promise<BonusResult> {
  const resp = await fetch(`/api/v1/superadmin/shops/${shopId}/credits/bonus/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new CreditsApiError(resp.status, await parseBody(resp));
  return (await resp.json()) as BonusResult;
}
