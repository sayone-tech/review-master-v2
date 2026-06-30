---
paths:
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
---

# Frontend Test Rules (Vitest + React Testing Library)

Scope: embedded React widget tests under `frontend/src/widgets/`.

- Descriptive test names: `should [expected] when [condition]`.
- Test **behavior, not implementation** — query by role/text/label (`getByRole`, `findByText`), not by class names or component internals. Assert what the user sees/does.
- **Mock external dependencies, not internal components.** Stub `fetch`/the API layer and the Django **bootstrap-data handoff** (the `window`/`data-*` props the widget reads), not sibling components or hooks.
- Render the real widget tree; reserve mocks for the network boundary and browser APIs.
- Clean up side effects in `afterEach` (timers, listeners, `vi.restoreAllMocks()`); RTL auto-unmounts, but reset module/network mocks.
- No real network calls — every request goes through a mock. Keep tests deterministic (no reliance on timing/animation).
- Match the brand/widget conventions in CLAUDE.md §26 (Vite-per-widget entrypoint, Tailwind) when asserting rendered output.
