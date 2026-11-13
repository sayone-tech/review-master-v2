import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateOrgModal } from "./CreateOrgModal";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  document.cookie = "csrftoken=test-csrf";
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function postedBody(): Record<string, unknown> {
  const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  const init = calls[calls.length - 1][1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

async function fillRequiredFields() {
  await userEvent.type(screen.getByTestId("field-name"), "Acme Co");
  await userEvent.selectOptions(screen.getByTestId("field-org_type"), "RETAIL");
  await userEvent.type(screen.getByTestId("field-email"), "acme@example.com");
  await userEvent.type(screen.getByTestId("field-number_of_stores"), "5");
}

describe("CreateOrgModal", () => {
  it("lists the placeholder plus 10 org types in order with labels", () => {
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={() => {}} />);
    const opts = Array.from(
      (screen.getByTestId("field-org_type") as HTMLSelectElement).options,
    ).map((o) => [o.value, o.textContent]);
    expect(opts).toEqual([["", "Select a type"], ...[
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
]]);
  });

  it("client-side validation blocks submit when fields invalid", async () => {
    const onCreated = vi.fn();
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={onCreated} />);
    // Submit the form directly (jsdom does not support form= attribute cross-element)
    const form = document.getElementById("create-org-form") as HTMLFormElement;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(await screen.findByText(/Name must be 2–100 characters\./)).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("successful submit dispatches exact toast with recipient email", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 201 }),
    );
    const listener = vi.fn();
    window.addEventListener("app:toast", listener as EventListener);
    const onCreated = vi.fn();
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={onCreated} />);
    await userEvent.type(screen.getByTestId("field-name"), "Acme Co");
    await userEvent.selectOptions(screen.getByTestId("field-org_type"), "RETAIL");
    await userEvent.type(screen.getByTestId("field-email"), "acme@example.com");
    await userEvent.type(screen.getByTestId("field-number_of_stores"), "5");
    await userEvent.click(screen.getByTestId("create-submit"));
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    const detail = (listener.mock.calls[0][0] as CustomEvent).detail as {
      title: string;
    };
    expect(detail.title).toBe(
      "Organisation created. Invitation email sent to acme@example.com.",
    );
    expect(postedBody().monthly_credit_allocation).toBe(0);
    window.removeEventListener("app:toast", listener as EventListener);
  });

  it("duplicate email API error renders exact inline message", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ email: ["already in use"] }), {
        status: 400,
      }),
    );
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={() => {}} />);
    await userEvent.type(screen.getByTestId("field-name"), "Acme Co");
    await userEvent.selectOptions(screen.getByTestId("field-org_type"), "RETAIL");
    await userEvent.type(screen.getByTestId("field-email"), "dup@example.com");
    await userEvent.type(screen.getByTestId("field-number_of_stores"), "5");
    await userEvent.click(screen.getByTestId("create-submit"));
    expect(
      await screen.findByText("An organisation with this email already exists."),
    ).toBeInTheDocument();
  });

  it("should default monthly credits per shop to 0 with the helper and the off hint", () => {
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={() => {}} />);
    const input = screen.getByLabelText("Monthly credits per shop") as HTMLInputElement;
    expect(input).toHaveAttribute("data-testid", "field-monthly_credit_allocation");
    expect(input.value).toBe("0");
    const wrapper = document.getElementById(input.getAttribute("aria-describedby") as string);
    expect(wrapper).toHaveTextContent(
      "Each shop in this organisation gets this many credits at the start of every month. Unused credits lapse.",
    );
    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "0 means AI replies are off for this organisation.",
    );
  });

  it("should show the immediate hint and post the value when a positive allocation is entered", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 201 }),
    );
    const onCreated = vi.fn();
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={onCreated} />);
    await fillRequiredFields();
    const input = screen.getByLabelText("Monthly credits per shop");
    await userEvent.clear(input);
    await userEvent.type(input, "25");

    expect(screen.getByTestId("credit-allocation-hint")).toHaveTextContent(
      "Takes effect immediately for this month.",
    );

    await userEvent.click(screen.getByTestId("create-submit"));
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(postedBody().monthly_credit_allocation).toBe(25);
  });

  it("should block submit with the inline error when the allocation is out of range", async () => {
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={() => {}} />);
    await fillRequiredFields();
    const input = screen.getByLabelText("Monthly credits per shop");
    await userEvent.clear(input);
    await userEvent.type(input, "10001");
    expect(screen.getByTestId("credit-allocation-hint")).toBeEmptyDOMElement();
    await userEvent.click(screen.getByTestId("create-submit"));

    expect(
      await screen.findByText("Enter a whole number between 0 and 10,000."),
    ).toHaveAttribute("role", "alert");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("should render a server error keyed monthly_credit_allocation under the field", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify({
          monthly_credit_allocation: ["Ensure this value is less than or equal to 10000."],
        }),
        { status: 400 },
      ),
    );
    render(<CreateOrgModal open={true} onClose={() => {}} onCreated={() => {}} />);
    await fillRequiredFields();
    await userEvent.click(screen.getByTestId("create-submit"));

    expect(
      await screen.findByText("Ensure this value is less than or equal to 10000."),
    ).toBeInTheDocument();
  });
});
