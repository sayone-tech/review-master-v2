import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditOrgModal } from "./EditOrgModal";
import type { OrgRow } from "./types";

function makeOrg(overrides: Partial<OrgRow> = {}): OrgRow {
  return {
    id: 7,
    name: "Acme Co",
    org_type: "RETAIL",
    email: "acme@example.com",
    address: "",
    number_of_stores: 5,
    status: "ACTIVE",
    created_at: "2026-01-01T00:00:00Z",
    total_stores: 2,
    active_stores: 2,
    activation_status: "active",
    last_invited_at: null,
    allow_custom_sync_depth: false,
    monthly_credit_allocation: 100,
    current_month_credit_allocation: 100,
    ...overrides,
  };
}

function fetchMock() {
  return fetch as unknown as ReturnType<typeof vi.fn>;
}

function lastRequestBody(): Record<string, unknown> {
  const calls = fetchMock().mock.calls;
  const init = calls[calls.length - 1][1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  document.cookie = "csrftoken=test-csrf";
  // Fake only Date so user-event keeps real timers.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-15T12:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function setCredits(value: string) {
  const input = screen.getByLabelText("Monthly credits per shop");
  await userEvent.clear(input);
  if (value !== "") await userEvent.type(input, value);
}

describe("EditOrgModal monthly credits per shop", () => {
  it("shows the deferred hint and sends the new allocation when Superadmin changes 100 to 50", async () => {
    fetchMock().mockResolvedValue(new Response(JSON.stringify({ id: 7 }), { status: 200 }));
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    await setCredits("50");

    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "Takes effect on 1 Dec 2026. Shops keep 100 this month.",
    );

    await userEvent.click(screen.getByTestId("edit-submit"));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock().mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/organisations/7/");
    expect(init.method).toBe("PATCH");
    expect(lastRequestBody().monthly_credit_allocation).toBe(50);
  });

  it("shows the immediate hint when the saved and current-month values are both 0", async () => {
    render(
      <EditOrgModal
        org={makeOrg({ monthly_credit_allocation: 0, current_month_credit_allocation: 0 })}
        onClose={() => {}}
        onUpdated={() => {}}
      />,
    );
    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "0 means AI replies are off for this organisation.",
    );

    await setCredits("50");

    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "Takes effect immediately for this month.",
    );
  });

  it("keeps the deferred hint keyed on this month's value when saved is 0 but shops still hold 100", async () => {
    render(
      <EditOrgModal
        org={makeOrg({ monthly_credit_allocation: 0, current_month_credit_allocation: 100 })}
        onClose={() => {}}
        onUpdated={() => {}}
      />,
    );

    await setCredits("50");

    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "Takes effect on 1 Dec 2026. Shops keep 100 this month.",
    );
  });

  it("shows the turn-off copy in the amber note when a positive allocation is set to 0", async () => {
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    await setCredits("0");

    const hint = screen.getByTestId("credit-allocation-hint");
    expect(hint).toHaveTextContent(
      "Takes effect on 1 Dec 2026. Shops keep 100 this month, then AI replies turn off.",
    );
    expect(hint).toHaveClass("bg-amber-tint");
  });

  it("shows no live hint and omits the allocation from the PATCH when the value is unchanged", async () => {
    fetchMock().mockResolvedValue(new Response(JSON.stringify({ id: 7 }), { status: 200 }));
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    expect(screen.getByTestId("credit-allocation-hint")).toBeEmptyDOMElement();

    const name = screen.getByTestId("edit-field-name");
    await userEvent.clear(name);
    await userEvent.type(name, "Acme Renamed");
    await userEvent.click(screen.getByTestId("edit-submit"));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const body = lastRequestBody();
    expect(body.name).toBe("Acme Renamed");
    expect(body).not.toHaveProperty("monthly_credit_allocation");
  });

  it("blocks submit with an inline error when the value is out of range", async () => {
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    await setCredits("10001");
    expect(screen.getByTestId("credit-allocation-hint")).toBeEmptyDOMElement();
    await userEvent.click(screen.getByTestId("edit-submit"));

    expect(
      await screen.findByText("Enter a whole number between 0 and 10,000."),
    ).toHaveAttribute("role", "alert");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("blocks submit when the field is empty", async () => {
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    await setCredits("");
    await userEvent.click(screen.getByTestId("edit-submit"));

    expect(
      await screen.findByText("Enter a whole number between 0 and 10,000."),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("renders the server field error under the credits field", async () => {
    fetchMock().mockResolvedValue(
      new Response(
        JSON.stringify({
          monthly_credit_allocation: ["Ensure this value is less than or equal to 10000."],
        }),
        { status: 400 },
      ),
    );
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    await setCredits("500");
    await userEvent.click(screen.getByTestId("edit-submit"));

    expect(
      await screen.findByText("Ensure this value is less than or equal to 10000."),
    ).toBeInTheDocument();
  });

  it("labels the input and describes it by the helper text", () => {
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);

    const input = screen.getByLabelText("Monthly credits per shop");
    expect(input).toHaveAttribute("data-testid", "edit-field-monthly_credit_allocation");
    const describedBy = input.getAttribute("aria-describedby") as string;
    const wrapper = document.getElementById(describedBy) as HTMLElement;
    expect(wrapper).toHaveTextContent(
      "Each shop in this organisation gets this many credits at the start of every month. Unused credits lapse.",
    );
    expect(wrapper).toContainElement(screen.getByTestId("credit-allocation-hint"));
    expect(screen.getByTestId("credit-allocation-hint")).toHaveAttribute("role", "status");
  });
});

describe("EditOrgModal org types", () => {
  it("lists 10 org types in order with labels", () => {
    render(<EditOrgModal org={makeOrg()} onClose={() => {}} onUpdated={() => {}} />);
    const opts = Array.from(
      (screen.getByTestId("edit-field-org_type") as HTMLSelectElement).options,
    ).map((o) => [o.value, o.textContent]);
    expect(opts).toEqual([
  ["RETAIL", "Retail"],
  ["RESTAURANT", "Restaurant & Cafe"],
  ["PHARMACY", "Pharmacy"],
  ["SUPERMARKET", "Supermarket"],
  ["CLINIC", "Clinic"],
  ["HOSPITAL", "Hospital"],
  ["SALON", "Salon"],
  ["SPA", "Spa"],
  ["HOTEL_RESORT", "Hotel & Resort"],
  ["GYM_FITNESS", "Gym & Fitness"],
]);
  });
});
