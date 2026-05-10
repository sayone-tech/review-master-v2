import type { TargetCreatePayload, TargetRow, TargetUpdatePayload } from "./types";

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

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new ApiError(resp.status, data);
  }
  if (resp.status === 204) return null as T;
  return resp.json() as Promise<T>;
}

export async function listTargets(shopId: number): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return handle<TargetRow[]>(resp);
}

export async function createTarget(
  shopId: number,
  payload: TargetCreatePayload,
): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function patchTarget(
  shopId: number,
  targetId: number,
  payload: TargetUpdatePayload,
): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function deleteTarget(shopId: number, targetId: number): Promise<void> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  return handle<void>(resp);
}
