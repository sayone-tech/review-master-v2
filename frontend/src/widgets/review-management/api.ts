import type {
  ReviewFilterParams,
  ReviewListResponse,
  ReviewRow,
  ReviewStats,
  SyncingResponse,
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
  ) {
    super(`API error ${status}`);
  }
}

async function handle(resp: Response): Promise<unknown> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new ApiError(resp.status, data);
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

export async function fetchReviewStats(params?: ReviewFilterParams): Promise<ReviewStats> {
  const qs = params ? buildQs(params) : "";
  const resp = await fetch(`/api/v1/reviews/stats/${qs}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ReviewStats;
}

export async function fetchSyncingShops(): Promise<SyncingResponse> {
  const resp = await fetch(`/api/v1/shops/syncing/`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as SyncingResponse;
}
