/**
 * Reads the Django credit contact json_script bootstrap rendered on the
 * Shops and Reviews pages: `{"organisation_name": "...", "support_email": "..."}`.
 *
 * Never throws: a missing or malformed script yields empty strings so the Buy
 * More modal still opens (the mailto then has no recipient, which the caller
 * can treat as "contact unavailable").
 */
export interface CreditContact {
  organisationName: string;
  supportEmail: string;
}

const EMPTY_CONTACT: CreditContact = { organisationName: "", supportEmail: "" };

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function readCreditContact(): CreditContact {
  try {
    const el = document.getElementById("credit-contact");
    if (!el || !el.textContent) return { ...EMPTY_CONTACT };
    const data: unknown = JSON.parse(el.textContent);
    if (typeof data !== "object" || data === null) return { ...EMPTY_CONTACT };
    const record = data as Record<string, unknown>;
    return {
      organisationName: asString(record.organisation_name),
      supportEmail: asString(record.support_email),
    };
  } catch {
    return { ...EMPTY_CONTACT };
  }
}
