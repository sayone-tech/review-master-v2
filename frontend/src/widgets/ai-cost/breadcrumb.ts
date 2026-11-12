// The AI Cost crumb lives in the shared top bar (`#topbar-breadcrumb`, outside the React root).
// Platform view: "AI Cost". Organisation view: "AI Cost / {name}", where "AI Cost" links back
// with the current filters; a plain left click is handled client-side.

const LINK_CLS = "font-medium text-muted underline-offset-2 hover:text-ink hover:underline";

export interface CostCrumb {
  name: string | null;
  href: string;
  onBack: () => void;
}

export function applyCostCrumb(crumb: CostCrumb | null): () => void {
  const el = document.getElementById("topbar-breadcrumb");
  if (!el) return () => {};
  if (!crumb) {
    el.textContent = "AI Cost";
    return () => {};
  }
  const link = document.createElement("a");
  link.href = crumb.href;
  link.className = LINK_CLS;
  link.textContent = "AI Cost";
  const onClick = (e: MouseEvent) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    crumb.onBack();
  };
  link.addEventListener("click", onClick);
  const nodes: Node[] = [link];
  if (crumb.name) {
    const sep = document.createElement("span");
    sep.className = "mx-1.5 font-normal text-faint";
    sep.setAttribute("aria-hidden", "true");
    sep.textContent = "/";
    nodes.push(sep, document.createTextNode(crumb.name));
  }
  el.replaceChildren(...nodes);
  return () => link.removeEventListener("click", onClick);
}
