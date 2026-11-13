import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { OrgDetail } from "./OrgDetail";

afterEach(() => vi.unstubAllGlobals());

const filters = { range: "7d" as const };

describe("OrgDetail", () => {
  it("renders 'Organisation not found' on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ code: "organisation_not_found", detail: "Organisation not found." }), { status: 404 })),
    );
    const onOrgName = vi.fn();
    render(<OrgDetail orgId={99} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} onOrgName={onOrgName} />);
    expect(await screen.findByText("Organisation not found")).toBeInTheDocument();
    expect(onOrgName).toHaveBeenCalledWith(null);
  });

  it("not-found back link keeps the query and intercepts plain left clicks only", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    const onBack = vi.fn();
    render(<OrgDetail orgId={99} filters={filters} onFilters={vi.fn()} onBack={onBack} />);
    await screen.findByText("Organisation not found");
    const link = screen.getByRole("link", { name: /Back to AI Cost/ });
    expect(link).toHaveAttribute("href", "/admin/ai-cost/?range=7d");
    link.addEventListener("click", (e) => e.preventDefault()); // avoid jsdom navigation
    fireEvent.click(link, { ctrlKey: true });
    expect(onBack).not.toHaveBeenCalled();
    fireEvent.click(link);
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

const summary = (calls: number) => ({
  organisation: { id: 7, name: "Acme", org_type: "RETAIL", shop_count: 1 },
  range: { key: "7d", start: "2026-11-05T00:00:00Z", end: "2026-11-12T00:00:00Z" },
  generated_at: new Date().toISOString(),
  totals: {
    calls, success_calls: calls, failed_calls: 0, moderated_calls: 0,
    input_tokens: 500, output_tokens: 200, cost: "2.000000", org_count: 1, active_shops: 1,
  },
});
const shopsBody = (next: string | null = null) => ({
  count: 40, next, previous: null, generated_at: new Date().toISOString(),
  unattributed: { calls: 1, input_tokens: 5, output_tokens: 5, cost: "0.500000", by_request_type: {} },
  results: [
    { shop_id: 3, name: "High St", region_name: "North", calls: 2, input_tokens: 1000,
      output_tokens: 400, cost: "4.000000", by_request_type: { enrichment: "3.000000" } },
  ],
});
const modelsBody = {
  generated_at: new Date().toISOString(),
  results: [{ model: "gpt-test", calls: 1, input_tokens: 500, output_tokens: 200, cost: "4.000000" }],
};

function mockApi(calls: number) {
  const fetchMock = vi.fn(async (url: string) => {
    const body = url.includes("/summary/")
      ? summary(calls)
      : url.includes("/shops/")
        ? shopsBody("http://x/?page=2")
        : modelsBody;
    return new Response(JSON.stringify(body), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
const shopUrls = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.map((c) => c[0] as string).filter((u) => u.includes("/shops/"));

describe("OrgDetail loaded states", () => {
  it("shows the active-shop count in the Total Cost footer", async () => {
    mockApi(5);
    render(<OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} />);
    expect(await screen.findByText("Across 1 active shop")).toBeInTheDocument();
  });

  it("renders header, KPIs, shop and model rows", async () => {
    mockApi(1);
    render(<OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} />);
    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Acme" })).toBeInTheDocument();
    expect(screen.getByText("Retail")).toBeInTheDocument();
    expect(screen.getByText("1 shop, 1 active in this period")).toBeInTheDocument();
    for (const l of ["Total cost", "API calls", "Input tokens", "Output tokens"])
      expect(screen.getAllByText(l).length).toBeGreaterThan(0);
    expect(await screen.findByText("High St")).toBeInTheDocument();
    expect(screen.getByText("North")).toBeInTheDocument();
    expect(screen.getByText("Cost by model")).toBeInTheDocument();
    expect(await screen.findByText("gpt-test")).toBeInTheDocument();
  });

  it("shows the empty state and Reset filter switches to this_month", async () => {
    mockApi(0);
    const onFilters = vi.fn();
    render(<OrgDetail orgId={7} filters={filters} onFilters={onFilters} onBack={vi.fn()} />);
    expect(
      await screen.findByText("No AI usage for this organisation in the selected period"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Reset filter" }));
    expect(onFilters).toHaveBeenCalledWith({ range: "this_month" });
  });

  it("sorting changes the request sort param, resets to page 1 and sets aria-sort", async () => {
    const m = mockApi(1);
    render(<OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} />);
    await screen.findByText("High St");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(shopUrls(m).some((u) => u.includes("page=2"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: /^API calls/ }));
    await waitFor(() => {
      const last = shopUrls(m).at(-1)!;
      expect(last).toContain("sort=calls");
      expect(last).toContain("page=1");
    });
    expect(screen.getAllByRole("columnheader", { name: /API calls/ })[0]).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("keeps Unattributed last across a page change", async () => {
    const m = mockApi(1);
    render(<OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} />);
    await screen.findByText("High St");
    const lastRow = () => within(screen.getAllByRole("table")[0]).getAllByRole("row").at(-1)!;
    expect(lastRow()).toHaveTextContent("Unattributed");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(shopUrls(m).some((u) => u.includes("page=2"))).toBe(true));
    await waitFor(() => expect(screen.getByRole("button", { name: "2" })).toHaveAttribute("aria-current", "page"));
    expect(lastRow()).toHaveTextContent("Unattributed");
  });

  it("shows the server-provided name in the header before the summary loads", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(
      <OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} initialName="Acme" />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "Acme" })).toBeInTheDocument();
  });

  it("reports the organisation name, or null on 404, for the breadcrumb", async () => {
    mockApi(1);
    const onOrgName = vi.fn();
    render(<OrgDetail orgId={7} filters={filters} onFilters={vi.fn()} onBack={vi.fn()} onOrgName={onOrgName} />);
    await waitFor(() => expect(onOrgName).toHaveBeenCalledWith("Acme"));
  });

  it("keeps the shops table when the models request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/models/")) return new Response("{}", { status: 500 });
        const body = url.includes("/summary/") ? summary(1) : shopsBody();
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
    render(<OrgDetail orgId={7} filters={{ range: "7d" }} onFilters={() => {}} onBack={() => {}} />);
    expect(await screen.findByText("High St")).toBeInTheDocument();
    expect(await screen.findByText(/Could not load model costs/)).toBeInTheDocument();
  });
});
