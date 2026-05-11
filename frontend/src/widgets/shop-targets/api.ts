import type { TargetRow, SetTargetPayload, TargetHistoryRow } from "./types";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function reqHeaders(method: string): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (method !== "GET") h["X-CSRFToken"] = getCsrfToken();
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
  const data =
    resp.status === 204 ? (undefined as T) : ((await resp.json().catch(() => null)) as T);
  if (!resp.ok) throw new ApiError(resp.status, data);
  return data;
}

export async function listTargets(shopId: number): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    credentials: "same-origin",
    headers: reqHeaders("GET"),
  });
  return handle<TargetRow[]>(resp);
}

export async function setTarget(
  shopId: number,
  payload: SetTargetPayload,
): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    method: "POST",
    credentials: "same-origin",
    headers: reqHeaders("POST"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow[]>(resp);
}

export async function deleteTarget(shopId: number, targetId: number): Promise<void> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: reqHeaders("DELETE"),
  });
  return handle<void>(resp);
}

export async function fetchTargetHistory(
  shopId: number,
  periodType: "WEEK" | "MONTH",
): Promise<TargetHistoryRow[]> {
  const resp = await fetch(
    `/api/v1/shops/${shopId}/targets/history/?period_type=${periodType}`,
    { credentials: "same-origin", headers: reqHeaders("GET") },
  );
  return handle<TargetHistoryRow[]>(resp);
}
