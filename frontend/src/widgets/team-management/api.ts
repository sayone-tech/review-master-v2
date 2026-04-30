import type {
  TeamCreatePayload,
  TeamFilterParams,
  TeamListResponse,
  TeamMemberRow,
  TeamStats,
  TeamUpdatePayload,
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

function buildQs(params: TeamFilterParams): string {
  const u = new URLSearchParams();
  if (params.search) u.set("search", params.search);
  if (params.region_id !== undefined) u.set("region_id", String(params.region_id));
  if (params.shop_id !== undefined) u.set("shop_id", String(params.shop_id));
  if (params.page) u.set("page", String(params.page));
  if (params.page_size) u.set("page_size", String(params.page_size));
  const qs = u.toString();
  return qs ? `?${qs}` : "";
}

export async function listTeam(params: TeamFilterParams = {}): Promise<TeamListResponse> {
  const resp = await fetch(`/api/v1/team/${buildQs(params)}`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return (await handle(resp)) as TeamListResponse;
}

export async function createTeamMember(payload: TeamCreatePayload): Promise<TeamMemberRow> {
  const resp = await fetch("/api/v1/team/", {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as TeamMemberRow;
}

export async function updateTeamMember(
  id: number,
  payload: TeamUpdatePayload,
): Promise<TeamMemberRow> {
  const resp = await fetch(`/api/v1/team/${id}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as TeamMemberRow;
}

export async function disableTeamMember(id: number): Promise<TeamMemberRow> {
  const resp = await fetch(`/api/v1/team/${id}/disable/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
  });
  return (await handle(resp)) as TeamMemberRow;
}

export async function enableTeamMember(id: number): Promise<TeamMemberRow> {
  const resp = await fetch(`/api/v1/team/${id}/enable/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
  });
  return (await handle(resp)) as TeamMemberRow;
}

export async function resendTeamInvitation(id: number): Promise<TeamMemberRow> {
  const resp = await fetch(`/api/v1/team/${id}/resend/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
  });
  return (await handle(resp)) as TeamMemberRow;
}

export async function removeTeamMember(id: number): Promise<null> {
  const resp = await fetch(`/api/v1/team/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  return (await handle(resp)) as null;
}

export async function getTeamStats(): Promise<TeamStats> {
  const resp = await fetch("/api/v1/team/stats/", {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return (await handle(resp)) as TeamStats;
}
