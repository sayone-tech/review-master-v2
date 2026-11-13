import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BuyMoreCreditsModal } from "./BuyMoreCreditsModal";
import { readCreditContact } from "./contact";

function mountBootstrap(payload: unknown): void {
  const el = document.createElement("script");
  el.id = "credit-contact";
  el.type = "application/json";
  el.textContent = JSON.stringify(payload);
  document.body.appendChild(el);
}

function params(href: string): { subject: string; body: string } {
  const query = href.slice(href.indexOf("?") + 1);
  const map: Record<string, string> = {};
  for (const part of query.split("&")) {
    const eq = part.indexOf("=");
    map[part.slice(0, eq)] = decodeURIComponent(part.slice(eq + 1));
  }
  return { subject: map.subject, body: map.body };
}

describe("BuyMoreCreditsModal tracer (bootstrap -> mailto)", () => {
  beforeEach(() => {
    mountBootstrap({ organisation_name: "Acme", support_email: "support@reviewbee.in" });
  });

  afterEach(() => {
    document.getElementById("credit-contact")?.remove();
  });

  it("should open an encoded Contact Admin mailto to support when given the bootstrap and a shop", () => {
    const contact = readCreditContact();
    render(
      <BuyMoreCreditsModal
        open
        onClose={() => {}}
        organisationName={contact.organisationName}
        supportEmail={contact.supportEmail}
        shop={{
          name: "Downtown",
          remaining: 35,
          total: 100,
          isEnabled: true,
          periodLabel: "November 2026",
        }}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Buy More Credits" })).toBeInTheDocument();

    const link = screen.getByRole("link", { name: "Contact Admin" });
    const href = link.getAttribute("href") as string;
    expect(href.startsWith("mailto:support@reviewbee.in?subject=")).toBe(true);
    expect(href).toContain("%0D%0A");

    const { subject, body } = params(href);
    expect(subject).toBe("Credit request — Acme / Downtown");
    expect(body).toContain("Organisation: Acme");
    expect(body).toContain("Shop: Downtown");
    expect(body).toContain("Month: November 2026");
    expect(body).toContain("Current balance: 35 of 100 credits remaining");
    expect(body).toContain("Credits needed:");
  });
});

describe("BuyMoreCreditsModal states", () => {
  const baseProps = {
    organisationName: "Acme",
    supportEmail: "support@reviewbee.in",
  };

  it("should show the purchase paragraph and the support address fallback for an enabled shop", () => {
    render(
      <BuyMoreCreditsModal
        open
        onClose={() => {}}
        {...baseProps}
        shop={{ name: "Downtown", remaining: 3, total: 10, isEnabled: true }}
      />,
    );
    expect(
      screen.getByText(
        "To purchase additional credits for this month, please contact your Review Bear administrator. Your administrator will add credits as soon as possible.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("support@reviewbee.in")).toBeInTheDocument();
    expect(screen.getByText(/If your email app doesn't open, write to/)).toBeInTheDocument();
  });

  it("should show the not-enabled paragraph when the shop is not enabled", () => {
    render(
      <BuyMoreCreditsModal
        open
        onClose={() => {}}
        {...baseProps}
        shop={{ name: "Downtown", isEnabled: false }}
      />,
    );
    expect(
      screen.getByText(
        "AI replies aren't enabled for this shop yet. To turn them on, please contact your Review Bear administrator. Your administrator will add credits as soon as possible.",
      ),
    ).toBeInTheDocument();
  });

  it("should render an org-only mailto when no shop context is given", () => {
    render(<BuyMoreCreditsModal open onClose={() => {}} {...baseProps} />);
    const href = screen.getByRole("link", { name: "Contact Admin" }).getAttribute("href") as string;
    expect(decodeURIComponent(href)).toContain("subject=Credit request \u2014 Acme&body=");
    expect(decodeURIComponent(href)).not.toContain("Shop:");
  });

  it("should render nothing when closed", () => {
    render(<BuyMoreCreditsModal open={false} onClose={() => {}} {...baseProps} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("BuyMoreCreditsModal accessibility", () => {
  const props = {
    organisationName: "Acme",
    supportEmail: "support@reviewbee.in",
    shop: { name: "Downtown", remaining: 35, total: 100, isEnabled: true },
  };

  it("should expose a modal dialog labelled Buy More Credits", () => {
    render(<BuyMoreCreditsModal open onClose={() => {}} {...props} />);
    const dialog = screen.getByRole("dialog", { name: "Buy More Credits" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("should call onClose when Escape is pressed", async () => {
    const onClose = vi.fn();
    render(<BuyMoreCreditsModal open onClose={onClose} {...props} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("should call onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(<BuyMoreCreditsModal open onClose={onClose} {...props} />);
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("should call onClose when the X button is clicked", async () => {
    const onClose = vi.fn();
    render(<BuyMoreCreditsModal open onClose={onClose} {...props} />);
    await userEvent.click(screen.getByTestId("modal-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("should call onClose when the Close button is clicked", async () => {
    const onClose = vi.fn();
    render(<BuyMoreCreditsModal open onClose={onClose} {...props} />);
    // The shell X button also has the accessible name "Close"; the footer one is the text button.
    const footerClose = screen
      .getAllByRole("button", { name: "Close" })
      .find((el) => el.textContent === "Close") as HTMLElement;
    await userEvent.click(footerClose);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("should keep Tab focus inside the dialog", async () => {
    // jsdom has no layout, so tabbable would treat every element as hidden; stub the browser API.
    vi.spyOn(Element.prototype, "getClientRects").mockReturnValue([
      {} as DOMRect,
    ] as unknown as DOMRectList);
    try {
      render(<BuyMoreCreditsModal open onClose={() => {}} {...props} />);
      const dialog = screen.getByRole("dialog", { name: "Buy More Credits" });
      for (let i = 0; i < 6; i += 1) {
        await userEvent.tab();
        expect(dialog.contains(document.activeElement)).toBe(true);
      }
    } finally {
      vi.restoreAllMocks();
    }
  });

  it("should not close when Contact Admin is clicked", async () => {
    const onClose = vi.fn();
    render(<BuyMoreCreditsModal open onClose={onClose} {...props} />);
    const link = screen.getByRole("link", { name: "Contact Admin" });
    // jsdom does not navigate to mailto: URLs; prevent default so the test stays quiet.
    link.addEventListener("click", (e) => e.preventDefault());
    await userEvent.click(link);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("BuyMoreCreditsModal has no payment flow", () => {
  it("should render no form controls, price text or delivery-time promise", () => {
    render(
      <BuyMoreCreditsModal
        open
        onClose={() => {}}
        organisationName="Acme"
        supportEmail="support@reviewbee.in"
        shop={{ name: "Downtown", remaining: 1, total: 100, isEnabled: true }}
      />,
    );
    const dialog = screen.getByRole("dialog", { name: "Buy More Credits" });
    expect(dialog.querySelector("input, select, textarea")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
    const text = dialog.textContent ?? "";
    expect(text).not.toMatch(/[$\u20B9\u20AC\u00A3]/);
    expect(text.toLowerCase()).not.toContain("price");
    expect(text.toLowerCase()).not.toContain("checkout");
    expect(text).not.toContain("24 hours");
    expect(text.toLowerCase()).not.toMatch(/within \d+ ?(hours|days|minutes)/);
  });
});
