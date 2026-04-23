import type {
  CreateOrgPayload,
  ListResponse,
  OrgRow,
  UpdateOrgPayload,
} from "./types";

const BASE = "/api/v1/organisations/";

export function getCsrfToken(): string {
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
  status: number;
  fieldErrors: Record<string, string[]>;
  constructor(
    status: number,
    fieldErrors: Record<string, string[]> = {},
    message = "API error",
  ) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

async function handle(resp: Response): Promise<unknown> {
  if (resp.ok) {
    if (resp.status === 204) return null;
    return resp.json();
  }
  let fieldErrors: Record<string, string[]> = {};
  try {
    fieldErrors = (await resp.json()) as Record<string, string[]>;
  } catch {
    // non-JSON error body
  }
  throw new ApiError(resp.status, fieldErrors, `HTTP ${resp.status}`);
}

export async function listOrgs(queryString: string): Promise<ListResponse> {
  const qs = queryString.startsWith("?") ? queryString.slice(1) : queryString;
  const url = qs ? `${BASE}?${qs}` : BASE;
  const resp = await fetch(url, {
    method: "GET",
    headers: headers("GET"),
    credentials: "same-origin",
  });
  return (await handle(resp)) as ListResponse;
}

export async function createOrg(payload: CreateOrgPayload): Promise<OrgRow> {
  const resp = await fetch(BASE, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as OrgRow;
}

export async function updateOrg(
  id: number,
  payload: UpdateOrgPayload,
): Promise<OrgRow> {
  const resp = await fetch(`${BASE}${id}/`, {
    method: "PATCH",
    headers: headers("PATCH"),
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as OrgRow;
}

export async function deleteOrg(id: number): Promise<void> {
  const resp = await fetch(`${BASE}${id}/`, {
    method: "DELETE",
    headers: headers("DELETE"),
    credentials: "same-origin",
  });
  await handle(resp);
}

export async function resendInvitation(id: number): Promise<void> {
  const resp = await fetch(`${BASE}${id}/resend-invitation/`, {
    method: "POST",
    headers: headers("POST"),
    credentials: "same-origin",
  });
  await handle(resp);
}
