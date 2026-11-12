import type { Paginated, PriceRow, PriceSummary } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const BASE = "/api/v1/superadmin/ai-pricing";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function toError(resp: Response): Promise<ApiError> {
  let detail = `HTTP ${resp.status}`;
  try {
    const body = (await resp.json()) as Record<string, unknown>;
    const raw = body["detail"] ?? body["error"];
    if (typeof raw === "string") detail = raw;
  } catch {
    /* ignore */
  }
  return new ApiError(resp.status, detail);
}

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url, { credentials: "same-origin" });
  if (!resp.ok) throw await toError(resp);
  return resp.json() as Promise<T>;
}

export function fetchPriceSummary(page: number): Promise<Paginated<PriceSummary>> {
  return getJson(`${BASE}/?page=${page}`);
}

/** Every price row for a model, following pagination (bounded by price changes per model). */
export async function fetchHistory(model: string): Promise<Paginated<PriceRow>> {
  const rows: PriceRow[] = [];
  let page = 1;
  for (;;) {
    const r = await getJson<Paginated<PriceRow>>(
      `${BASE}/history/?model=${encodeURIComponent(model)}&page_size=100&page=${page}`,
    );
    rows.push(...r.results);
    if (!r.next) return { count: rows.length, next: null, previous: null, results: rows };
    page += 1;
  }
}

export async function deleteScheduledPrice(id: number): Promise<void> {
  const resp = await fetch(`${BASE}/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": getCsrfToken() },
  });
  if (!resp.ok) throw await toError(resp);
}
