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

  it("should list the platform actor as one Review Bear Admin option when the server sends it", () => {
    render(
      <AuditLogFilters
        filters={{}}
        actors={[
          { id: 7, full_name: "Sayone Admin" },
          { id: 8, full_name: "Anna Admin" },
          { id: "platform", full_name: "Review Bear Admin" },
        ]}
        onApply={() => {}}
        onReset={() => {}}
        hasActiveFilters={false}
      />,
    );
    expect(screen.getByRole("option", { name: "Review Bear Admin" })).toHaveValue("platform");
    expect(screen.getByRole("option", { name: "Sayone Admin" })).toHaveValue("7");
    const names = screen.getAllByRole("option").map((o) => o.textContent);
    // System, then the platform actor, then people by name.
    expect(names.slice(names.indexOf("System"))).toEqual([
      "System",
      "Review Bear Admin",
      "Anna Admin",
      "Sayone Admin",
    ]);
  });

  it("should not offer Credits when the viewer is Staff", () => {
    renderFilters(false);
    expect(screen.queryByRole("option", { name: "Credits" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Replies" })).toBeInTheDocument();
  });
});
