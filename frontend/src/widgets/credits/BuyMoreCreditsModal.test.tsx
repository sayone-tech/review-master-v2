import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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
