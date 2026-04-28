import type { CreateRegionPayload, RegionBlockedError, RegionRow, UpdateRegionPayload } from "./types";

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

export async function listRegions(): Promise<RegionRow[]> {
  const resp = await fetch("/api/v1/regions/", {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  const data = (await handle(resp)) as { results?: RegionRow[] } | RegionRow[];
  // Handle both paginated (DRF PageNumberPagination) and plain array responses
  if (Array.isArray(data)) return data;
  return (data as { results: RegionRow[] }).results ?? [];
}

export async function createRegion(payload: CreateRegionPayload): Promise<RegionRow> {
  const resp = await fetch("/api/v1/regions/", {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as RegionRow;
}

export async function updateRegion(id: number, payload: UpdateRegionPayload): Promise<RegionRow> {
  const resp = await fetch(`/api/v1/regions/${id}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as RegionRow;
}

export async function deleteRegion(id: number): Promise<void | RegionBlockedError> {
  const resp = await fetch(`/api/v1/regions/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  if (resp.status === 409) {
    const body = (await resp.json()) as RegionBlockedError;
    return body; // caller checks: if (result && "shop_count" in result) → blocked
  }
  await handle(resp);
}
