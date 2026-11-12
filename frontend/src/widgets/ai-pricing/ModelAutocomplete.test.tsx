import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelAutocomplete } from "./ModelAutocomplete";
import * as api from "./api";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchSuggestions: vi.fn(),
}));

function Harness({ initial = "" }: { initial?: string }) {
  const [v, setV] = useState(initial);
  return (
    <>
      <ModelAutocomplete id="m" value={v} onChange={setV} />
      <output data-testid="value">{v}</output>
    </>
  );
}

const sug = (model: string, has_price: boolean) => ({ model, last_used_at: null, has_price });

describe("ModelAutocomplete", () => {
  beforeEach(() => vi.mocked(api.fetchSuggestions).mockReset());

  it("lists unpriced models first with a red No pricing label", async () => {
    vi.mocked(api.fetchSuggestions).mockResolvedValue({
      results: [sug("priced-a", true), sug("unpriced-b", false)],
    });
    render(<Harness />);
    await userEvent.click(screen.getByRole("combobox"));
    const opts = await screen.findAllByRole("option");
    expect(opts[0]).toHaveTextContent("unpriced-b");
    expect(opts[0]).toHaveTextContent("⚠ No pricing");
    expect(opts[1]).toHaveTextContent("priced-a");
    expect(opts[1]).not.toHaveTextContent("No pricing");
    expect(screen.getByText("⚠ No pricing")).toHaveClass("text-red");
  });

  it("debounces typing into a single request with the final query", async () => {
    vi.mocked(api.fetchSuggestions).mockResolvedValue({ results: [] });
    render(<Harness />);
    await userEvent.type(screen.getByRole("combobox"), "gpt");
    await waitFor(() => expect(api.fetchSuggestions).toHaveBeenCalledWith("gpt"));
    expect(api.fetchSuggestions).not.toHaveBeenCalledWith("g");
    expect(api.fetchSuggestions).not.toHaveBeenCalledWith("gp");
  });

  it("accepts free text and selecting a suggestion fills the value", async () => {
    vi.mocked(api.fetchSuggestions).mockResolvedValue({ results: [sug("gpt-x", false)] });
    render(<Harness />);
    await userEvent.type(screen.getByRole("combobox"), "brand-new-model");
    expect(screen.getByTestId("value")).toHaveTextContent("brand-new-model");
    await userEvent.clear(screen.getByRole("combobox"));
    await userEvent.type(screen.getByRole("combobox"), "gpt");
    await userEvent.click(await screen.findByRole("option", { name: /gpt-x/ }));
    expect(screen.getByTestId("value")).toHaveTextContent("gpt-x");
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("ignores an out-of-order older response", async () => {
    let resolveFirst!: (v: { results: ReturnType<typeof sug>[] }) => void;
    vi.mocked(api.fetchSuggestions)
      .mockReturnValueOnce(new Promise((r) => (resolveFirst = r)))
      .mockResolvedValueOnce({ results: [sug("fresh", true)] });
    render(<Harness />);
    const box = screen.getByRole("combobox");
    await userEvent.type(box, "a");
    await waitFor(() => expect(api.fetchSuggestions).toHaveBeenCalledTimes(1));
    await userEvent.type(box, "b");
    expect(await screen.findByRole("option", { name: /fresh/ })).toBeInTheDocument();
    resolveFirst({ results: [sug("stale", true)] });
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("option", { name: /stale/ })).not.toBeInTheDocument();
  });
});
