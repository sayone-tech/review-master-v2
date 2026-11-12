import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RequestTypeBadges } from "./RequestTypeBadges";

describe("RequestTypeBadges", () => {
  it("renders every key including unknown types", () => {
    render(
      <RequestTypeBadges
        costs={{ enrichment: "5.000000", reply: "2.500000", summary: "1.000000" }}
      />,
    );
    expect(screen.getByText(/enrichment/i)).toBeTruthy();
    expect(screen.getByText(/reply/i)).toBeTruthy();
    expect(screen.getByText(/summary/i)).toBeTruthy();
    expect(screen.getByText(/\$5\.00/)).toBeTruthy();
  });
});
