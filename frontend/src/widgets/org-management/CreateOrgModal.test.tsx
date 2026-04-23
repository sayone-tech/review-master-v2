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

describe("CreateOrgModal", () => {
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
});
