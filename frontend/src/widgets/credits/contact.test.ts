import { afterEach, describe, expect, it } from "vitest";
import { readCreditContact } from "./contact";

function mountRaw(text: string): void {
  const el = document.createElement("script");
  el.id = "credit-contact";
  el.type = "application/json";
  el.textContent = text;
  document.body.appendChild(el);
}

describe("readCreditContact", () => {
  afterEach(() => {
    document.getElementById("credit-contact")?.remove();
  });

  it("should return both fields when the bootstrap is valid", () => {
    mountRaw(JSON.stringify({ organisation_name: "Acme", support_email: "support@reviewbee.in" }));
    expect(readCreditContact()).toEqual({
      organisationName: "Acme",
      supportEmail: "support@reviewbee.in",
    });
  });

  it("should return empty strings when the script is missing", () => {
    expect(readCreditContact()).toEqual({ organisationName: "", supportEmail: "" });
  });

  it("should return empty strings when the JSON is malformed", () => {
    mountRaw("{not json");
    expect(readCreditContact()).toEqual({ organisationName: "", supportEmail: "" });
  });

  it("should return empty strings when the JSON is not an object", () => {
    mountRaw("null");
    expect(readCreditContact()).toEqual({ organisationName: "", supportEmail: "" });
  });

  it("should map non-string values to empty strings", () => {
    mountRaw(JSON.stringify({ organisation_name: 42, support_email: { a: 1 } }));
    expect(readCreditContact()).toEqual({ organisationName: "", supportEmail: "" });
  });
});
