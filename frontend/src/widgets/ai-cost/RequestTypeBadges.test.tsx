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
    expect(screen.getByText("Enrichment").parentElement).toHaveTextContent("$5.00000000");
  });

  it("humanises real request-type keys", () => {
    render(
      <RequestTypeBadges
        costs={{ enrichment: "1.000000", reply_generation: "2.000000", tag_merge: "3.000000" }}
      />,
    );
    expect(screen.getByText("Enrichment")).toBeTruthy();
    expect(screen.getByText("Reply")).toBeTruthy();
    expect(screen.getByText("Tag Merge")).toBeTruthy();
    expect(screen.queryByText(/reply_generation/i)).toBeNull();
  });
});
