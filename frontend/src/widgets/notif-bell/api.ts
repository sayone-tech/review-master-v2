import type { BellResponse } from "./types";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
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

export async function getBell(): Promise<BellResponse> {
  const resp = await fetch("/api/v1/notifications/bell/", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  });
  return (await handle(resp)) as BellResponse;
}

export async function markRead(id: number): Promise<void> {
  const resp = await fetch(`/api/v1/notifications/${id}/read/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
  });
  await handle(resp);
}

export async function markAllRead(): Promise<void> {
  const resp = await fetch("/api/v1/notifications/mark-all-read/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    credentials: "same-origin",
  });
  await handle(resp);
}
