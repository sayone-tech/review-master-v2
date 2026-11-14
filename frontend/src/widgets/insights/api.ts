import type { InsightItem, InsightsBookData } from "./types";

export class ApiError extends Error {
  constructor(public status: number) {
    super(`API error ${status}`);
  }
}

/** Read-only, same-origin, session-authenticated (GET needs no CSRF token). */
export async function fetchInsights(signal?: AbortSignal): Promise<InsightsBookData> {
  const resp = await fetch("/api/v1/insights/", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!resp.ok) throw new ApiError(resp.status);
  return (await resp.json()) as InsightsBookData;
}

/** The Reviews page URL with the insight's filters and date window pinned. */
export function reviewsHref(link: InsightItem["link"]): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(link)) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  return `/admin/org/reviews/?${params.toString()}`;
}
