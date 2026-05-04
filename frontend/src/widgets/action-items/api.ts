import type {
  ActionItemDetail,
  ActionItemNote,
  ActionItemStatus,
  CreateActionItemPayload,
  ListParams,
  PaginatedActionItems,
  UpdatePayload,
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

function buildQs(params: ListParams): string {
  const u = new URLSearchParams();
  u.set("page", String(params.page));
  u.set("page_size", String(params.page_size));
  u.set("ordering", params.ordering);
  if (params.shop !== undefined) u.set("shop", String(params.shop));
  if (params.status) u.set("status", params.status);
  if (params.scope) u.set("scope", params.scope);
  if (params.assignee) u.set("assignee", params.assignee);
  if (params.from_date) u.set("from_date", params.from_date);
  if (params.to_date) u.set("to_date", params.to_date);
  if (params.search) u.set("search", params.search);
  if (params.review !== undefined) u.set("review", String(params.review));
  return `?${u.toString()}`;
}

export async function listActionItems(params: ListParams): Promise<PaginatedActionItems> {
  const resp = await fetch(`/api/v1/action-items/${buildQs(params)}`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as PaginatedActionItems;
}

export async function getActionItem(id: number): Promise<ActionItemDetail> {
  const resp = await fetch(`/api/v1/action-items/${id}/`, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ActionItemDetail;
}

export async function createActionItem(
  payload: CreateActionItemPayload,
): Promise<ActionItemDetail> {
  const resp = await fetch(`/api/v1/action-items/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as ActionItemDetail;
}

export async function updateActionItem(
  id: number,
  payload: Partial<UpdatePayload>,
): Promise<ActionItemDetail> {
  const resp = await fetch(`/api/v1/action-items/${id}/`, {
    method: "PATCH",
    headers: headers("PATCH"),
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as ActionItemDetail;
}

export async function transitionStatus(
  id: number,
  status: ActionItemStatus,
): Promise<ActionItemDetail> {
  const resp = await fetch(`/api/v1/action-items/${id}/transition-status/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify({ status }),
  });
  return (await handle(resp)) as ActionItemDetail;
}

export async function addNote(id: number, body: string): Promise<ActionItemNote> {
  const resp = await fetch(`/api/v1/action-items/${id}/add-note/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify({ body }),
  });
  return (await handle(resp)) as ActionItemNote;
}
