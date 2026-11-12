import { formatCount } from "../org-management/creditHint";

/**
 * Shop context for a credit request. Deliberately carries no review data
 * (CLAUDE.md §22: review text is user PII and must never reach a mailto).
 */
export interface CreditRequestShop {
  name: string;
  remaining?: number;
  total?: number;
  isEnabled?: boolean;
  periodLabel?: string;
}

/** Replace CR/LF runs with one space so a name can never add mail lines (D-14). */
function sanitiseName(value: string): string {
  return value.replace(/[\r\n]+/g, " ").trim();
}

/**
 * Build the Contact Admin mailto (D-13..D-15). Always addressed to the
 * platform support email; every subject/body value is URL-encoded and the
 * intended line breaks are CRLF.
 */
export function buildCreditRequestMailto(args: {
  supportEmail: string;
  organisationName: string;
  shop?: CreditRequestShop;
}): string {
  const org = sanitiseName(args.organisationName);
  const shop = args.shop;
  const shopName = shop ? sanitiseName(shop.name) : "";

  const subject = shop ? `Credit request — ${org} / ${shopName}` : `Credit request — ${org}`;

  const lines: string[] = [
    "Hello ReviewBee team,",
    "",
    "I'd like to request more AI reply credits.",
    "",
    `Organisation: ${org}`,
  ];

  if (shop) {
    lines.push(`Shop: ${shopName}`);
    if (typeof shop.periodLabel === "string" && shop.periodLabel !== "") {
      lines.push(`Month: ${sanitiseName(shop.periodLabel)}`);
    }
    if (shop.isEnabled === false) {
      lines.push("Current balance: AI replies are not enabled for this shop");
    } else if (Number.isFinite(shop.remaining) && Number.isFinite(shop.total)) {
      lines.push(
        `Current balance: ${formatCount(shop.remaining as number)} of ${formatCount(shop.total as number)} credits remaining`,
      );
    }
  }

  lines.push("Credits needed:", "", "Thank you.");

  const body = lines.join("\r\n");
  const encodedSubject = encodeURIComponent(subject);
  const encodedBody = encodeURIComponent(body);
  return `mailto:${args.supportEmail}?subject=${encodedSubject}&body=${encodedBody}`;
}
