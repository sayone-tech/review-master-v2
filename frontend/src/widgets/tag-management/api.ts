// Phase 25-03 — Tag Management API calls.
// Endpoints built in 25-02: /api/v1/reviews/canonical-tags/ + /api/v1/reviews/tag-merge-jobs/

import type {
  FetchTagsParams,
  OrgCanonicalTagRow,
  PaginatedTagResponse,
  TagMergeJobRow,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(`API error ${status}`);
  }
}

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new ApiError(resp.status, data);
  }
  if (resp.status === 204) return null as unknown as T;
  return resp.json() as Promise<T>;
}

export async function fetchTags(params: FetchTagsParams = {}): Promise<PaginatedTagResponse> {
  const qs = new URLSearchParams();
  if (params.ordering) qs.set("ordering", params.ordering);
  if (params.page !== undefined) qs.set("page", String(params.page));
  if (params.page_size !== undefined) qs.set("page_size", String(params.page_size));
  const url = `/api/v1/reviews/canonical-tags/${qs.toString() ? "?" + qs.toString() : ""}`;
  const resp = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  });
  return handle<PaginatedTagResponse>(resp);
}

export async function renameTag(id: number, label: string): Promise<OrgCanonicalTagRow> {
  const resp = await fetch(`/api/v1/reviews/canonical-tags/${id}/rename/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
    body: JSON.stringify({ label }),
  });
  // Surface non-2xx so caller can detect 400-duplicate error
  return handle<OrgCanonicalTagRow>(resp);
}

export async function startMerge(
  sourceId: number,
  targetId: number,
): Promise<{ job_id: number }> {
  const resp = await fetch(`/api/v1/reviews/canonical-tags/${sourceId}/merge/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
    body: JSON.stringify({ target_id: targetId }),
  });
  // Surface non-2xx so caller can detect 409-conflict
  return handle<{ job_id: number }>(resp);
}

export async function fetchActiveJob(): Promise<TagMergeJobRow | null> {
  const resp = await fetch("/api/v1/reviews/tag-merge-jobs/active/", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  });
  return handle<TagMergeJobRow | null>(resp);
}

export async function dismissMergeJob(id: number): Promise<void> {
  const resp = await fetch(`/api/v1/reviews/tag-merge-jobs/${id}/dismiss/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
  });
  await handle<void>(resp);
}
