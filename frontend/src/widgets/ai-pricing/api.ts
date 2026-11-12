import type {
  MissingResponse,
  Paginated,
  PriceRow,
  PriceSummary,
  SuggestionsResponse,
} from "./types";

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  public code?: string;
  public fields?: FieldErrors;
  constructor(
    public status: number,
    message: string,
    extra: { code?: string; fields?: FieldErrors } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = extra.code;
    this.fields = extra.fields;
  }
}

export const BASE = "/api/v1/superadmin/ai-pricing";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function toError(resp: Response): Promise<ApiError> {
  let detail = `HTTP ${resp.status}`;
  let code: string | undefined;
  let fields: FieldErrors | undefined;
  try {
    const body = (await resp.json()) as Record<string, unknown>;
    const raw = body["detail"] ?? body["error"];
    if (typeof raw === "string") detail = raw;
    if (typeof body["code"] === "string") code = body["code"];
    if (raw === undefined) {
      // DRF field errors: {field: [message, ...]}
      const entries = Object.entries(body).filter(
        (e): e is [string, string[]] => Array.isArray(e[1]) && e[1].every((m) => typeof m === "string"),
      );
      if (entries.length > 0) fields = Object.fromEntries(entries);
    }
  } catch {
    /* ignore */
  }
  return new ApiError(resp.status, detail, { code, fields });
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

export interface CreatePriceBody {
  model: string;
  input_token_price_per_1m: string;
  output_token_price_per_1m: string;
  cached_token_price_per_1m: string;
  /** ISO 8601 UTC with a `Z` suffix; the server reads a naive datetime as UTC. */
  effective_from: string;
}

export async function createPrice(body: CreatePriceBody): Promise<PriceRow> {
  const resp = await fetch(`${BASE}/`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw await toError(resp);
  return resp.json() as Promise<PriceRow>;
}

export function fetchSuggestions(q: string): Promise<SuggestionsResponse> {
  return getJson(`${BASE}/model-suggestions/?q=${encodeURIComponent(q)}`);
}

export function fetchMissing(): Promise<MissingResponse> {
  return getJson(`${BASE}/missing/`);
}

export async function refreshMissing(): Promise<MissingResponse> {
  const resp = await fetch(`${BASE}/missing/refresh/`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRFToken": getCsrfToken() },
  });
  if (!resp.ok) throw await toError(resp);
  return resp.json() as Promise<MissingResponse>;
}
