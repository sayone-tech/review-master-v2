import type {
  ShopCreatePayload,
  ShopFilterParams,
  ShopRow,
  ShopUpdatePayload,
  ShopsListResponse,
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

function buildQs(params: ShopFilterParams): string {
  const u = new URLSearchParams();
  if (params.search) u.set("search", params.search);
  if (params.status) u.set("status", params.status);
  if (params.region !== undefined && params.region !== "") u.set("region", String(params.region));
  if (params.page) u.set("page", String(params.page));
  if (params.page_size) u.set("page_size", String(params.page_size));
  const qs = u.toString();
  return qs ? `?${qs}` : "";
}

export async function listShops(params: ShopFilterParams = {}): Promise<ShopsListResponse> {
  const resp = await fetch(`/api/v1/shops/${buildQs(params)}`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return (await handle(resp)) as ShopsListResponse;
}

export async function createShop(payload: ShopCreatePayload): Promise<ShopRow> {
  const resp = await fetch("/api/v1/shops/", {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as ShopRow;
}

export async function updateShop(id: number, payload: ShopUpdatePayload): Promise<ShopRow> {
  const resp = await fetch(`/api/v1/shops/${id}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as ShopRow;
}

export async function activateShop(id: number): Promise<ShopRow> {
  const resp = await fetch(`/api/v1/shops/${id}/activate/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
  });
  return (await handle(resp)) as ShopRow;
}

export async function deactivateShop(id: number): Promise<ShopRow> {
  const resp = await fetch(`/api/v1/shops/${id}/deactivate/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
  });
  return (await handle(resp)) as ShopRow;
}

export async function reconnectShop(id: number, state: string): Promise<ShopRow> {
  const resp = await fetch(`/api/v1/shops/${id}/reconnect/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify({ state }),
  });
  return (await handle(resp)) as ShopRow;
}

export async function getOAuthResult(
  state: string,
): Promise<{ listings: unknown[] } | null> {
  const resp = await fetch(
    `/api/v1/shops/oauth_result/?state=${encodeURIComponent(state)}`,
    {
      credentials: "same-origin",
      headers: headers("GET"),
    },
  );
  if (resp.status === 204) return null;
  return (await handle(resp)) as { listings: unknown[] };
}
