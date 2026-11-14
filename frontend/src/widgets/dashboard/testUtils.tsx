import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

/** Render inside a fresh QueryClient; hook-level `retry: 1` retries instantly. */
export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, retryDelay: 0 } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Matches an element whose full text content is exactly `text`. */
export function exactText(text: string) {
  return (_: string, el: Element | null) => el?.textContent === text;
}
