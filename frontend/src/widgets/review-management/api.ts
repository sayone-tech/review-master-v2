import type {
  ReviewFilterParams,
  ReviewListResponse,
  ReviewRow,
  ReviewStats,
  SyncingResponse,
  TagOption,
} from "./types";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function headers(method: string): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (method !== "GET" && method !== "HEAD") {
    h["X-CSRFToken"] = getCsrfToken();
  }
  return h;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
    public retryAfterSeconds?: number,
  ) {
    super(`API error ${status}`);
  }
}

function parseRetryAfter(resp: Response, data: unknown): number | undefined {
  // WR-02: surface Retry-After to callers so the UI can show "try again in X seconds".
  // Prefer the HTTP header; fall back to parsing DRF's `detail` ("Expected available in N seconds.").
  const header = resp.headers.get("Retry-After");
  if (header) {
    const n = parseInt(header, 10);
    if (!Number.isNaN(n) && n >= 0) return n;
  }
  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      const m = detail.match(/in\s+(\d+)\s+seconds/i);
      if (m) return parseInt(m[1], 10);
    }
  }
  return undefined;
}

async function handle(resp: Response): Promise<unknown> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    const retryAfter = resp.status === 429 ? parseRetryAfter(resp, data) : undefined;
    throw new ApiError(resp.status, data, retryAfter);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function buildQs(params: ReviewFilterParams): string {
  const u = new URLSearchParams();
  if (params.search) u.set("search", params.search);
  if (params.shop !== undefined) u.set("shop", String(params.shop));
  if (params.rating !== undefined) u.set("rating", String(params.rating));
  if (params.sentiment) u.set("sentiment", params.sentiment);
  if (params.is_replied !== undefined) u.set("is_replied", params.is_replied ? "true" : "false");
  if (params.has_comment !== undefined) u.set("has_comment", params.has_comment ? "true" : "false");
  if (params.from_date) u.set("from_date", params.from_date);
  if (params.to_date) u.set("to_date", params.to_date);
  if (params.ordering) u.set("ordering", params.ordering);
  if (params.page_size) u.set("page_size", String(params.page_size));
  if (params.page && params.page > 1) u.set("page", String(params.page));
  if (params.tags && params.tags.length > 0) u.set("tags", params.tags.join(","));
  const qs = u.toString();
  return qs ? `?${qs}` : "";
}

export async function listReviews(params: ReviewFilterParams): Promise<ReviewListResponse> {
  const resp = await fetch(`/api/v1/reviews/${buildQs(params)}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReviewListResponse;
}

export async function submitReply(reviewId: number, comment: string): Promise<ReviewRow> {
  const resp = await fetch(`/api/v1/reviews/${reviewId}/reply/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify({ comment }),
  });
  return (await handle(resp)) as ReviewRow;
}

export async function deleteReply(reviewId: number): Promise<ReviewRow> {
  const resp = await fetch(`/api/v1/reviews/${reviewId}/reply/`, {
    method: "DELETE",
    headers: headers("DELETE"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReviewRow;
}

export async function fetchReviewStats(params?: ReviewFilterParams): Promise<ReviewStats> {
  const qs = params ? buildQs(params) : "";
  const resp = await fetch(`/api/v1/reviews/stats/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReviewStats;
}

export async function fetchTagList(shopId?: number): Promise<TagOption[]> {
  const qs = shopId ? `?shop=${shopId}` : "";
  const resp = await fetch(`/api/v1/reviews/tags/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as TagOption[];
}

export async function fetchSyncingShops(): Promise<SyncingResponse> {
  const resp = await fetch(`/api/v1/shops/syncing/`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as SyncingResponse;
}

export async function fetchSyncProgress(shopId: number): Promise<Record<string, unknown> | null> {
  const resp = await fetch(`/api/v1/reviews/sync-progress/${shopId}/`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  // Treat 404 as "no snapshot yet" — not an error condition for polling.
  if (resp.status === 404) return null;
  return (await handle(resp)) as Record<string, unknown>;
}

export async function generateReply(
  reviewId: number,
  tone: string,
  signal?: AbortSignal,
): Promise<{ draft: string }> {
  // IN-04: callers pass an AbortSignal so they can cancel an in-flight
  // request (e.g., user re-clicks a different tone or closes the composer).
  const resp = await fetch(`/api/v1/reviews/${reviewId}/generate-reply/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify({ tone }),
    signal,
  });
  return (await handle(resp)) as { draft: string };
}
