export interface NavSummary {
  reviews_awaiting_reply: number;
  open_action_items: number;
  credits: { remaining: number; total: number } | null;
}

type FoldStorage = Pick<Storage, "getItem" | "setItem">;

const FOLD_KEY = "rb.nav.folded";

const LINK_ACTIVE = ["bg-yellow", "text-black", "font-semibold"];
const LINK_INACTIVE = [
  "font-medium",
  "text-[#D4D4D8]",
  "hover:text-white",
  "hover:bg-white/[0.06]",
];
const BADGE_ACTIVE = ["bg-black", "text-yellow", "lg:bg-black", "lg:text-yellow"];
const BADGE_INACTIVE = ["bg-[#27272A]", "text-[#E4E4E7]", "lg:bg-[#27272A]", "lg:text-[#E4E4E7]"];

function setFolded(sidebar: HTMLElement, key: string, folded: boolean): void {
  const toggle = sidebar.querySelector<HTMLElement>(
    `[data-nav-group="${key}"] [data-nav-group-toggle]`,
  );
  const list = sidebar.querySelector<HTMLElement>(`#nav-group-${key}`);
  if (!toggle || !list) return;
  toggle.setAttribute("aria-expanded", String(!folded));
  // Class, not the `hidden` attribute: the attribute rule lives in Tailwind's base layer with
  // !important and would beat the rail's `md:max-lg:block!` utility.
  list.classList.toggle("hidden", folded);
}

function openGroupOf(sidebar: HTMLElement, el: Element): void {
  const key = el.closest<HTMLElement>("[data-nav-group]")?.dataset.navGroup;
  if (key) setFolded(sidebar, key, false);
}

export function syncActiveItem(sidebar: HTMLElement, path: string): void {
  sidebar.querySelectorAll<HTMLAnchorElement>("nav a[href]").forEach((a) => {
    const href = a.getAttribute("href") ?? "";
    const isActive = href === "/" ? path === "/" : path.startsWith(href);
    const badge = a.querySelector("[data-nav-badge]");

    a.classList.remove(...(isActive ? LINK_INACTIVE : LINK_ACTIVE));
    a.classList.add(...(isActive ? LINK_ACTIVE : LINK_INACTIVE));
    badge?.classList.remove(...(isActive ? BADGE_INACTIVE : BADGE_ACTIVE));
    badge?.classList.add(...(isActive ? BADGE_ACTIVE : BADGE_INACTIVE));
    if (isActive) {
      a.setAttribute("aria-current", "page");
      openGroupOf(sidebar, a);
    } else {
      a.removeAttribute("aria-current");
    }
  });
}

function readFolded(storage: FoldStorage | null): string[] {
  try {
    const parsed: unknown = JSON.parse(storage?.getItem(FOLD_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === "string") : [];
  } catch {
    return [];
  }
}

export function restoreFolds(sidebar: HTMLElement, storage: FoldStorage | null): void {
  for (const key of readFolded(storage)) setFolded(sidebar, key, true);
  // The group holding the current page always stays open.
  sidebar.querySelectorAll("a[aria-current='page']").forEach((a) => openGroupOf(sidebar, a));
}

export function rememberFold(
  groupKey: string,
  folded: boolean,
  storage: FoldStorage | null,
): void {
  try {
    if (!storage) return;
    const keys = new Set(readFolded(storage));
    if (folded) keys.add(groupKey);
    else keys.delete(groupKey);
    storage.setItem(FOLD_KEY, JSON.stringify([...keys]));
  } catch {
    // storage unavailable: fold state simply isn't remembered
  }
}

export function toggleGroup(
  sidebar: HTMLElement,
  toggle: HTMLElement,
  storage: FoldStorage | null,
): void {
  const key = toggle.closest<HTMLElement>("[data-nav-group]")?.dataset.navGroup;
  if (!key) return;
  const folded = toggle.getAttribute("aria-expanded") === "true";
  setFolded(sidebar, key, folded);
  rememberFold(key, folded, storage);
}

export function formatBadge(n: number): string | null {
  if (!(n > 0)) return null;
  return n > 99 ? "99+" : String(n);
}

function setBadge(sidebar: HTMLElement, key: string, n: number | null): void {
  const text = n === null ? null : formatBadge(n);
  sidebar.querySelectorAll<HTMLElement>(`[data-nav-badge="${key}"]`).forEach((el) => {
    el.textContent = text ?? "";
    el.hidden = text === null;
  });
}

export function renderSummary(sidebar: HTMLElement, summary: NavSummary | null): void {
  setBadge(sidebar, "reviews", summary ? summary.reviews_awaiting_reply : null);
  setBadge(sidebar, "action_items", summary ? summary.open_action_items : null);

  const meter = sidebar.querySelector<HTMLElement>("[data-nav-credits]");
  if (!meter) return;
  const credits = summary?.credits ?? null;
  if (!credits) {
    meter.hidden = true;
    return;
  }
  const text = meter.querySelector<HTMLElement>("[data-nav-credits-text]");
  const bar = meter.querySelector<HTMLElement>("[data-nav-credits-bar]");
  if (text) {
    text.textContent = `${credits.remaining.toLocaleString()} of ${credits.total.toLocaleString()} left`;
  }
  if (bar) {
    const pct = credits.total > 0 ? (credits.remaining / credits.total) * 100 : 0;
    bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  }
  meter.hidden = false;
}

export async function refreshSummary(
  sidebar: HTMLElement,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  const url = sidebar.dataset.navSummaryUrl;
  if (!url) return;
  try {
    const res = await fetchImpl(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      renderSummary(sidebar, null);
      return;
    }
    renderSummary(sidebar, (await res.json()) as NavSummary);
  } catch {
    renderSummary(sidebar, null);
  }
}
