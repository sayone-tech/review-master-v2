# Stack Research: v0.4 Dashboard — Frontend Additions

**Domain:** React 19 embedded widget — bar chart, donut chart, parallel data fetch, URL filter state
**Researched:** 2026-05-07
**Confidence:** HIGH for chart library (verified via GitHub package.json); HIGH for TanStack Query React 19 peer dep; MEDIUM for URL state (no library needed — vanilla pattern confirmed)

---

## Context: What Already Exists (Do Not Re-add)

This milestone adds frontend-only packages to the existing Vite + React setup. Backend packages from previous milestones (see git history) are locked and must not be changed.

| Package | Pinned Version | Role |
| --- | --- | --- |
| `react` | 19.2.5 | UI framework |
| `react-dom` | 19.2.5 | DOM renderer |
| `typescript` | 5.7.2 | Type system |
| `vite` | 6.0.1 | Bundler |
| `tailwindcss` | 4.2.4 | Styling |
| `lucide-react` | 1.8.0 | Icons |
| `alpinejs` | 3.15.11 | Alpine (Django template reactivity — not used in React widgets) |

**Existing data fetching pattern:** vanilla `useEffect` + `fetch` + hand-rolled `useState` for loading/error. This is confirmed across `useActionItems.ts`, `useNotifications.ts`, and `useOrgs.ts`. The codebase has zero query management library overhead and a consistent, understood pattern.

---

## New Packages Required for This Milestone

### (A) Chart Library: Recharts

**Decision: `recharts@^3.8.1` — NOT Chart.js/react-chartjs-2, NOT Nivo, NOT Victory**

**React 19 compatibility:** Verified HIGH confidence. The recharts `package.json` on the `main` branch lists `"react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"` as a peer dependency. Version 3.x is the current stable series (3.8.1 released March 2026).

**Why Recharts over the alternatives:**

- **vs Chart.js + react-chartjs-2:** react-chartjs-2 5.3.1 (last published November 2025) still specifies `"react": "^16.8.0 || ^17.0.0 || ^18.0.0"` — React 19 not in the peer dep range. Installing it against React 19.2.5 produces peer dep warnings and may require `--legacy-peer-deps`. Chart.js itself uses Canvas rendering, which requires manual cleanup in React strict mode. Recharts uses SVG, which is managed purely by React's reconciler — no `ref.current.destroy()` bookkeeping needed.

- **vs Nivo (`@nivo/*`):** Nivo has an open GitHub issue for React 19 support (issue #2618) marked as requiring `--legacy-peer-deps`. It is a modular scoped package ecosystem (`@nivo/bar`, `@nivo/pie`, etc.) which adds npm workspace complexity for only two chart types. Bundle overhead per chart type is roughly equivalent to Recharts once tree-shaken.

- **vs Victory:** Low weekly download momentum compared to Recharts; not included in 2026 comparison guides. Peer dep status for React 19 unverified.

**Why Recharts specifically:**

1. JSX-native API — `<BarChart>`, `<PieChart>`, `<Bar>`, `<Cell>` compose exactly like React components. No configuration-object DSL to learn.
2. Both required chart types (horizontal `BarChart` with custom `Cell` fills, and `PieChart` with `innerRadius` for the donut) are in the core package — single install.
3. Recharts 3.x ships ES modules and is tree-shakeable by Vite. Only the chart components imported are included in the bundle.
4. Largest React chart library by weekly downloads (~1.8M/week as of 2026 comparison guides). Community examples and StackOverflow coverage are dense.

**Single package addition:**

`recharts@^3.8.1` — covers both the bar chart (Top Performing Outlets) and the donut chart (Sentiment Distribution). React 19 peer dep verified; JSX API; SVG rendering; tree-shakeable.

**Recharts component mapping to dashboard charts:**

- **Horizontal bar chart** (Best Performing Outlets): `<BarChart layout="vertical">` + `<Bar>` + per-bar `<Cell fill={...}>` for color thresholds. No `CartesianGrid` needed — clean horizontal bars only.
- **Donut chart** (Sentiment Distribution): `<PieChart>` + `<Pie innerRadius={60} outerRadius={90}>` + three `<Cell>` elements. Use `startAngle={90} endAngle={-270}` for clockwise rendering starting at 12 o'clock.

**No animation needed:** Set `isAnimationActive={false}` on `<Bar>` and `<Pie>`. Dashboard widgets mount once; the animation adds delay without UX value in a filter-driven reload.

---

### (B) Data Fetching: Vanilla useEffect + Fetch (No TanStack Query)

**Decision: Do NOT add TanStack Query. Continue the existing vanilla pattern.**

**Rationale:**

The existing codebase uses a consistent, well-understood pattern: `useEffect` + `fetch` + `useState` for loading/error/data in custom hooks (`useActionItems`, `useNotifications`, etc.). Every engineer working on this codebase knows this pattern. The dashboard adds 5 API calls — not dozens.

TanStack Query v5 (`@tanstack/react-query`) is React 19 compatible (peer dep is `"react": "^18 || ^19"`), but the cost of adding it is:

- ~13.4 KB gzipped added to every entrypoint that imports `QueryClientProvider`
- A new mental model: `QueryClient`, `QueryClientProvider`, cache keys, stale time, invalidation — none of which is established in the codebase
- A `QueryClientProvider` wrapper that must wrap the widget root — this changes the entrypoint pattern for dashboard widgets
- The existing widgets demonstrate that vanilla fetching handles loading, error, and refetch cleanly without a library

**What the dashboard actually needs from a "parallel fetch" perspective:**

The dashboard has 5 widgets that each fetch one endpoint independently. "Parallel" is achieved by simply mounting all 5 widgets simultaneously — each calls its own `useEffect` on mount and fires its `fetch` independently. The browser handles concurrent HTTP/2 requests to the same origin naturally. There is no shared state, no cross-widget cache invalidation, and no mutation — the exact conditions where TanStack Query adds the least value.

**Per-widget loading skeletons:** Each widget manages its own `isLoading` boolean from its custom hook. Skeleton rendering is a conditional in each widget's JSX — no library required.

**When to revisit this decision:** If a future milestone adds optimistic mutation, real-time invalidation across widgets, or infinite scroll — that is when TanStack Query earns its bundle cost.

---

### (C) URL State: Vanilla URLSearchParams + window.history.replaceState (No Library)

**Decision: Do NOT add `nuqs`, `use-url-search-params`, or React Router. Use vanilla browser APIs.**

**Why no library is needed:**

The dashboard filter bar manages 5 params: `region`, `store`, `range`, `from`, `to`. This is a read/write operation on `URLSearchParams` — a native browser API available in all modern browsers. The pattern is:

```typescript
// Read current filters from URL on mount
const params = new URLSearchParams(window.location.search);
const region = params.get("region") ?? "";

// Update a filter (replaceState avoids polluting history)
function setFilter(key: string, value: string | null) {
  const next = new URLSearchParams(window.location.search);
  if (value) {
    next.set(key, value);
  } else {
    next.delete(key);
  }
  window.history.replaceState(null, "", `?${next.toString()}`);
}
```

This is a 20-line utility. Adding `nuqs` (4.2 KB gzipped) or `react-router` (full navigation stack) for 5 filter params is gross over-engineering for an embedded Django widget that does not use a SPA router.

**Session persistence:** The existing pattern for session persistence (from the project context) is `sessionStorage`. Write the serialized filter object to `sessionStorage` on every change; read it on mount to seed the initial state if URL params are absent. This is also 10 lines of vanilla code.

**No `popstate` handling needed:** The filter bar uses `replaceState` (not `pushState`), so the browser back button does not navigate through filter states. The user navigates away with the Django nav links, which perform full-page navigations. `popstate` support would only matter in a SPA — this is a Django-templated page.

---

## What NOT to Add

| Avoid | Why | Use Instead |
| --- | --- | --- |
| `@tanstack/react-query` | 13.4 KB gzipped overhead; new mental model; no mutation or cross-widget invalidation needed | Vanilla `useEffect` + `fetch` (existing pattern) |
| `react-chartjs-2` + `chart.js` | react-chartjs-2 5.3.x peer dep range does not include React 19; Canvas rendering requires manual destroy lifecycle in React | `recharts` (SVG, React 19 verified) |
| `@nivo/bar` + `@nivo/pie` | Open React 19 issue (#2618); scoped package complexity for only two chart types | `recharts` (single package for both charts) |
| `victory` | Lower adoption; React 19 peer dep status unverified; JSX API similar to Recharts but less community support | `recharts` |
| `nuqs` / `use-url-search-params` | 4–8 KB gzipped for 5 filter params that need 20 lines of vanilla code; no SPA router in scope | `URLSearchParams` + `window.history.replaceState` |
| `react-router-dom` | Full navigation stack for a non-SPA Django-template page; no router context established in any existing widget | Vanilla URL APIs |
| `zustand` / `jotai` | Cross-widget state store for widgets that each have isolated state and communicate via URL | Each widget reads URL params independently on mount |
| `date-fns` / `dayjs` | Dashboard date range is fixed enum presets (7d, 30d, 90d, custom) plus ISO string inputs — no date arithmetic needed | `new Date()` + `toISOString().split("T")[0]` for ISO dates |

---

## Installation

```bash
# From the frontend/ directory
npm install recharts@^3.8.1
```

That is the only `npm install` required for this milestone.

---

## Alternatives Considered

| Category | Chosen | Alternative | Why Not Chosen |
| --- | --- | --- | --- |
| Chart library | `recharts@^3.8.1` | `react-chartjs-2@5.3.1` + `chart.js` | react-chartjs-2 peer dep excludes React 19; Canvas lifecycle overhead |
| Chart library | `recharts@^3.8.1` | `@nivo/bar` + `@nivo/pie` | React 19 issue open; multi-package complexity |
| Data fetching | Vanilla useEffect | `@tanstack/react-query` v5 | 13.4 KB gzipped overhead; no mutation or invalidation needed; adds unfamiliar abstraction to established codebase |
| Data fetching | Vanilla useEffect | `swr` | 4.2 KB gzipped but still introduces a new mental model for a problem the codebase already solves with 5 lines of hooks |
| URL state | Vanilla URLSearchParams | `nuqs` | Adds a package for a 20-line utility; no Next.js router context; not a SPA |
| URL state | Vanilla URLSearchParams | React Router `useSearchParams` | No router in scope; full navigation stack for 5 filter params |

---

## Version Compatibility

| Package | Version | React 19 Compatible | Notes |
| --- | --- | --- | --- |
| `recharts` | `^3.8.1` | YES — HIGH confidence | peerDeps include `^19.0.0` — verified GitHub main branch |
| `react-chartjs-2` | 5.3.1 | NO | peerDeps omit React 19; open issue #1235 |
| `@nivo/bar` / `@nivo/pie` | latest | PARTIAL | Requires `--legacy-peer-deps`; open issue #2618 |
| `@tanstack/react-query` | v5 (5.100.9) | YES | peerDeps include `^18` and `^19` — compatible but not added |

---

## Integration Notes for Vite

Recharts 3.x ships ES modules and is tree-shakeable. Import only what is used:

```typescript
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart, Pie, Cell as PieCell } from "recharts";
```

Vite's rollup bundler will tree-shake unused recharts internals. No Vite plugin configuration is required for recharts — it works out of the box with `@vitejs/plugin-react`.

**Entrypoint pattern:** The dashboard will follow the existing island pattern — one entrypoint file per widget in `frontend/src/entrypoints/`, each calling `ReactDOM.createRoot(...).render(...)`. Each widget reads URL params and session storage independently on mount. No shared root or provider wrapper is needed.

---

## Sources

- [recharts/recharts `package.json` — GitHub main branch](https://github.com/recharts/recharts/blob/main/package.json) — peerDependencies verified: React 16.8 || 17 || 18 || 19 — HIGH confidence
- [recharts releases — GitHub](https://github.com/recharts/recharts/releases) — v3.8.1 latest stable (March 2026)
- [react-chartjs-2 React 19 issue #1235 — GitHub](https://github.com/reactchartjs/react-chartjs-2/issues/1235) — React 19 not in peer dep range as of v5.3.1
- [nivo React 19 support issue #2618 — GitHub](https://github.com/plouc/nivo/issues/2618) — requires --legacy-peer-deps
- [@tanstack/react-query npm](https://www.npmjs.com/package/@tanstack/react-query) — v5 peer dep includes React 18 and 19 — HIGH confidence
- [Recharts vs Chart.js vs Nivo 2026 — PkgPulse](https://www.pkgpulse.com/guides/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026) — download volumes, bundle size comparison
- [TanStack Query parallel queries docs](https://tanstack.com/query/v5/docs/framework/react) — useQueries API confirmed; not adopted for this milestone
- [URLSearchParams + replaceState pattern — LogRocket 2025](https://blog.logrocket.com/advanced-react-state-management-using-url-parameters/) — vanilla URL state management confirmed
- [Best React chart libraries 2025 — LogRocket](https://blog.logrocket.com/best-react-chart-libraries-2025/) — Recharts pragmatic choice for standard dashboards

---

*Stack research for: v0.4 Dashboard — chart library, data fetching, URL filter state*
*Researched: 2026-05-07*
