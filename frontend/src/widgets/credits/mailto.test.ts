import { describe, expect, it } from "vitest";
import { buildCreditRequestMailto } from "./mailto";

const SUPPORT = "support@reviewbee.in";

function parse(href: string): { subject: string; body: string; raw: string } {
  const queryStart = href.indexOf("?");
  const query = href.slice(queryStart + 1);
  const [subjectPart, bodyPart] = query.split("&body=");
  return {
    subject: decodeURIComponent(subjectPart.replace(/^subject=/, "")),
    body: decodeURIComponent(bodyPart),
    raw: href,
  };
}

describe("buildCreditRequestMailto", () => {
  it("should omit shop, month and balance lines when there is no shop context", () => {
    const { subject, body } = parse(
      buildCreditRequestMailto({ supportEmail: SUPPORT, organisationName: "Acme" }),
    );
    expect(subject).toBe("Credit request — Acme");
    expect(body).toContain("Organisation: Acme");
    expect(body).toContain("Credits needed:");
    expect(body).not.toContain("Shop:");
    expect(body).not.toContain("Month:");
    expect(body).not.toContain("Current balance");
  });

  it("should omit the balance line when the total is unknown and the Month line when periodLabel is missing", () => {
    const { body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Acme",
        shop: { name: "Downtown", remaining: 4 },
      }),
    );
    expect(body).toContain("Shop: Downtown");
    expect(body).not.toContain("Current balance");
    expect(body).not.toContain("Month:");
  });

  it("should include the Month line when periodLabel is a non-empty string", () => {
    const { body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Acme",
        shop: { name: "Downtown", periodLabel: "November 2026" },
      }),
    );
    expect(body).toContain("Month: November 2026");
  });

  it("should state AI replies are not enabled when the shop is not enabled", () => {
    const { body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Acme",
        shop: { name: "Downtown", remaining: 0, total: 0, isEnabled: false },
      }),
    );
    expect(body).toContain("Current balance: AI replies are not enabled for this shop");
    expect(body).not.toContain("credits remaining");
  });

  it("should format the balance with thousands separators", () => {
    const { body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Acme",
        shop: { name: "Downtown", remaining: 1250, total: 10000, isEnabled: true },
      }),
    );
    expect(body).toContain("Current balance: 1,250 of 10,000 credits remaining");
  });

  it("should encode line breaks as %0D%0A and end the body with Thank you.", () => {
    const href = buildCreditRequestMailto({
      supportEmail: SUPPORT,
      organisationName: "Acme",
      shop: { name: "Downtown", remaining: 1, total: 2 },
    });
    const { body } = parse(href);
    expect(href).toContain("%0D%0A");
    expect(href).not.toMatch(/[\r\n]/);
    expect(body.endsWith("Thank you.")).toBe(true);
    expect(body.split("\r\n")[0]).toBe("Hello Review Bear team,");
  });

  it("should replace CR and LF in names with spaces so a name cannot add mail lines", () => {
    const { subject, body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Evil\r\nBcc: attacker@example.com",
        shop: { name: "Shop\nTwo\r\n\r\nThree" },
      }),
    );
    expect(subject).toBe("Credit request — Evil Bcc: attacker@example.com / Shop Two Three");
    expect(body).toContain("Organisation: Evil Bcc: attacker@example.com");
    expect(body).toContain("Shop: Shop Two Three");
    // Only the intended CRLF line breaks remain: no line starts with the injected header text.
    expect(body.split("\r\n").some((line) => line.startsWith("Bcc:"))).toBe(false);
  });

  it("should survive a decode round trip for &, ?, #, emoji and keep one ? and one &body= separator", () => {
    const org = "R&D? #1 \u{1F600} Co";
    const shop = "Café & Bar? #2 \u{1F355}";
    const href = buildCreditRequestMailto({
      supportEmail: SUPPORT,
      organisationName: org,
      shop: { name: shop },
    });
    const { subject, body } = parse(href);
    expect(subject).toBe(`Credit request — ${org} / ${shop}`);
    expect(body).toContain(`Organisation: ${org}`);
    expect(body).toContain(`Shop: ${shop}`);
    expect(href.split("?").length - 1).toBe(1);
    expect(href.split("&body=").length - 1).toBe(1);
    expect(href).not.toContain("#");
  });

  it("should round trip a 200-character shop name exactly", () => {
    const shop = "S".repeat(100) + "\u{1F600}" + "&?#".repeat(20) + "t".repeat(38);
    const href = buildCreditRequestMailto({
      supportEmail: SUPPORT,
      organisationName: "Acme",
      shop: { name: shop },
    });
    const { subject, body } = parse(href);
    expect(subject).toBe(`Credit request — Acme / ${shop}`);
    expect(body).toContain(`Shop: ${shop}`);
  });

  it("should accept no review data by signature: only organisation, shop and balance numbers appear", () => {
    const { subject, body } = parse(
      buildCreditRequestMailto({
        supportEmail: SUPPORT,
        organisationName: "Acme",
        shop: { name: "Downtown", remaining: 3, total: 10, isEnabled: true, periodLabel: "November 2026" },
      }),
    );
    const text = `${subject}\r\n${body}`.toLowerCase();
    for (const word of ["review text", "reviewer", "review id", "comment"]) {
      expect(text).not.toContain(word);
    }
    expect(body).not.toContain("Reviewer");
  });
});
