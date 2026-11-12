import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OrgDetail } from "./OrgDetail";

afterEach(() => vi.unstubAllGlobals());

const filters = { range: "7d" as const };

describe("OrgDetail", () => {
  it("renders 'Organisation not found' on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ code: "organisation_not_found", detail: "Organisation not found." }), { status: 404 })),
    );
    render(<OrgDetail orgId={99} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} />);
    expect(await screen.findByText("Organisation not found")).toBeInTheDocument();
  });

  it("back link keeps the query and intercepts plain left clicks", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    const onBack = vi.fn();
    render(<OrgDetail orgId={99} filters={filters} onFilters={vi.fn()} onBack={onBack} />);
    await screen.findByText("Organisation not found");
    const link = screen.getByRole("link", { name: /Back to AI Cost/ });
    expect(link).toHaveAttribute("href", "/admin/ai-cost/?range=7d");
    fireEvent.click(link);
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
