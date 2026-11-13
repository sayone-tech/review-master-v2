/** Count pill next to the page title in the black header (`#topbar-count`). */

export function setHeaderCount(n: number | null): void {
  const pill = document.getElementById("topbar-count");
  if (!pill) return;
  if (n === null || !Number.isFinite(n) || n < 0) {
    pill.hidden = true;
    pill.textContent = "";
    return;
  }
  pill.textContent = n.toLocaleString();
  pill.hidden = false;
}

function applyPageCount(): void {
  const raw = document.getElementById("main-content")?.dataset.pageCount;
  if (raw === undefined || raw === "") return;
  const n = Number(raw);
  if (Number.isFinite(n)) setHeaderCount(n);
}

/**
 * The header outlives Turbo navigations, so a count must not leak from the previous page.
 * Clear before the new body renders (so counts set by the new page's widgets survive), then
 * pick up an optional server-rendered `data-page-count`.
 */
export function registerHeaderNavigation(target: Document): void {
  target.addEventListener("turbo:before-render", () => setHeaderCount(null));
  target.addEventListener("turbo:load", applyPageCount);
}
