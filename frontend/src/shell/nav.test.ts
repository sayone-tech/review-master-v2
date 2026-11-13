import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  formatBadge,
  refreshSummary,
  renderSummary,
  restoreFolds,
  rememberFold,
  syncActiveItem,
  toggleGroup,
} from "./nav";

function group(key: string, hrefs: string[], badge?: string): string {
  return `<section data-nav-group="${key}">
    <button data-nav-group-toggle aria-expanded="true" aria-controls="nav-group-${key}"></button>
    <ul id="nav-group-${key}">${hrefs
      .map(
        (h) =>
          `<li><a href="${h}" class="font-medium text-[#D4D4D8]">x${
            badge ? `<span data-nav-badge="${badge}" hidden class="bg-[#27272A] text-[#E4E4E7]"></span>` : ""
          }</a></li>`,
      )
      .join("")}</ul></section>`;
}

let sidebar: HTMLElement;
beforeEach(() => {
  document.body.innerHTML = `<aside id="s" data-nav-summary-url="/api/v1/me/nav-summary/"><nav>
    ${group("work", ["/reviews/", "/action-items/"], "reviews")}
    ${group("insights", ["/reports/"])}</nav>
    <div data-nav-credits hidden><span data-nav-credits-text></span><div data-nav-credits-bar></div></div>
    <span data-nav-badge="action_items" hidden></span></aside>`;
  sidebar = document.getElementById("s")!;
});

const list = (k: string) => document.getElementById(`nav-group-${k}`)!;
const mem = (init?: string) => {
  const m = new Map<string, string>(init ? [["rb.nav.folded", init]] : []);
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
};

describe("syncActiveItem", () => {
  it("marks the matching link active and clears the previous one", () => {
    syncActiveItem(sidebar, "/reviews/");
    const a = sidebar.querySelector<HTMLElement>('a[href="/reviews/"]')!;
    expect(a.getAttribute("aria-current")).toBe("page");
    expect(a.classList.contains("bg-yellow")).toBe(true);
    syncActiveItem(sidebar, "/reports/");
    expect(a.hasAttribute("aria-current")).toBe(false);
    expect(a.classList.contains("bg-yellow")).toBe(false);
    expect(a.classList.contains("text-[#D4D4D8]")).toBe(true);
    expect(sidebar.querySelector('a[href="/reports/"]')!.getAttribute("aria-current")).toBe("page");
  });

  it("swaps badge colours with the active state", () => {
    syncActiveItem(sidebar, "/reviews/");
    const b = sidebar.querySelector('[data-nav-badge="reviews"]')!;
    expect(b.classList.contains("bg-black")).toBe(true);
    expect(b.classList.contains("bg-[#27272A]")).toBe(false);
  });

  it("opens a folded group when navigating into it", () => {
    toggleGroup(sidebar, sidebar.querySelector("[data-nav-group='insights'] button")!, null);
    expect(list("insights").hidden).toBe(true);
    syncActiveItem(sidebar, "/reports/");
    expect(list("insights").hidden).toBe(false);
  });
});

describe("fold memory", () => {
  it("restores folded groups from storage but keeps the active group open", () => {
    syncActiveItem(sidebar, "/reviews/");
    restoreFolds(sidebar, mem('["work","insights"]'));
    expect(list("work").hidden).toBe(false);
    expect(list("insights").hidden).toBe(true);
    expect(sidebar.querySelector("[data-nav-group='insights'] button")!.getAttribute("aria-expanded")).toBe("false");
  });

  it("renders the menu expanded when storage throws", () => {
    const bad = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
    expect(() => restoreFolds(sidebar, bad)).not.toThrow();
    expect(() => rememberFold("work", true, bad)).not.toThrow();
    expect(list("work").hidden).toBe(false);
    expect(list("insights").hidden).toBe(false);
  });

  it("toggleGroup persists the fold", () => {
    const s = mem();
    toggleGroup(sidebar, sidebar.querySelector("[data-nav-group='work'] button")!, s);
    expect(list("work").hidden).toBe(true);
    expect(s.getItem("rb.nav.folded")).toBe('["work"]');
    toggleGroup(sidebar, sidebar.querySelector("[data-nav-group='work'] button")!, s);
    expect(s.getItem("rb.nav.folded")).toBe("[]");
  });
});

describe("badges and meter", () => {
  it("formats badges: 0 hidden, 7, 99, 99+", () => {
    expect(formatBadge(0)).toBeNull();
    expect(formatBadge(7)).toBe("7");
    expect(formatBadge(99)).toBe("99");
    expect(formatBadge(100)).toBe("99+");
  });

  it("shows meter text 'X of Y left' with bar width X/Y and hides it when credits is null", () => {
    renderSummary(sidebar, { reviews_awaiting_reply: 3, open_action_items: 0, credits: { remaining: 1500, total: 2000 } });
    const meter = sidebar.querySelector<HTMLElement>("[data-nav-credits]")!;
    expect(meter.hidden).toBe(false);
    expect(sidebar.querySelector("[data-nav-credits-text]")!.textContent).toBe(`${(1500).toLocaleString()} of ${(2000).toLocaleString()} left`);
    expect(sidebar.querySelector<HTMLElement>("[data-nav-credits-bar]")!.style.width).toBe("75%");
    expect((sidebar.querySelector('[data-nav-badge="reviews"]') as HTMLElement).textContent).toBe("3");
    expect((sidebar.querySelector('[data-nav-badge="action_items"]') as HTMLElement).hidden).toBe(true);
    renderSummary(sidebar, { reviews_awaiting_reply: 0, open_action_items: 0, credits: null });
    expect(meter.hidden).toBe(true);
  });

  it("hides badges and meter when the fetch fails or returns 403", async () => {
    renderSummary(sidebar, { reviews_awaiting_reply: 3, open_action_items: 2, credits: { remaining: 1, total: 2 } });
    await refreshSummary(sidebar, vi.fn().mockResolvedValue({ ok: false, status: 403 }) as never);
    expect(sidebar.querySelector<HTMLElement>("[data-nav-credits]")!.hidden).toBe(true);
    expect(sidebar.querySelector<HTMLElement>('[data-nav-badge="reviews"]')!.hidden).toBe(true);
    renderSummary(sidebar, { reviews_awaiting_reply: 3, open_action_items: 2, credits: null });
    await refreshSummary(sidebar, vi.fn().mockRejectedValue(new Error("net")) as never);
    expect(sidebar.querySelector<HTMLElement>('[data-nav-badge="action_items"]')!.hidden).toBe(true);
  });

  it("does not fetch when the sidebar has no summary url (Superadmin)", async () => {
    delete sidebar.dataset.navSummaryUrl;
    const f = vi.fn();
    await refreshSummary(sidebar, f as never);
    expect(f).not.toHaveBeenCalled();
  });
});
