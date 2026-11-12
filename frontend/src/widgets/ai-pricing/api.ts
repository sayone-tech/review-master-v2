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

export function fetchHistory(model: string): Promise<Paginated<PriceRow>> {
  return getJson(`${BASE}/history/?model=${encodeURIComponent(model)}`);
}

export async function deleteScheduledPrice(id: number): Promise<void> {
  const resp = await fetch(`${BASE}/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": getCsrfToken() },
  });
  if (!resp.ok) throw await toError(resp);
}
