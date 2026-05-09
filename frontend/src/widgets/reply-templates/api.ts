import type { CreateTemplatePayload, TemplateRow, UpdateTemplatePayload } from "./types";

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

export async function listTemplates(): Promise<TemplateRow[]> {
  const resp = await fetch("/api/v1/reply-templates/", {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  const data = (await handle(resp)) as { results?: TemplateRow[] } | TemplateRow[];
  if (Array.isArray(data)) return data;
  return (data as { results: TemplateRow[] }).results ?? [];
}

export async function createTemplate(payload: CreateTemplatePayload): Promise<TemplateRow> {
  const resp = await fetch("/api/v1/reply-templates/", {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as TemplateRow;
}

export async function updateTemplate(
  id: number,
  payload: UpdateTemplatePayload,
): Promise<TemplateRow> {
  const resp = await fetch(`/api/v1/reply-templates/${id}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as TemplateRow;
}

export async function deleteTemplate(id: number): Promise<void> {
  const resp = await fetch(`/api/v1/reply-templates/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  await handle(resp);
}
