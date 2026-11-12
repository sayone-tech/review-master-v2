import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuditLogFilters } from "./AuditLogFilters";

// CVIS-06: the Credits type option is offered to Org Admins only.
function renderFilters(showCreditsType?: boolean) {
  render(
    <AuditLogFilters
      filters={{}}
      actors={[]}
      onApply={() => {}}
      onReset={() => {}}
      hasActiveFilters={false}
      showCreditsType={showCreditsType}
    />,
  );
}

describe("AuditLogFilters Credits type option", () => {
  it("should offer Credits when the viewer is an Org Admin", () => {
    renderFilters(true);
    expect(screen.getByRole("option", { name: "Credits" })).toBeInTheDocument();
  });

  it("should not offer Credits when the viewer is Staff", () => {
    renderFilters(false);
    expect(screen.queryByRole("option", { name: "Credits" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Replies" })).toBeInTheDocument();
  });
});
