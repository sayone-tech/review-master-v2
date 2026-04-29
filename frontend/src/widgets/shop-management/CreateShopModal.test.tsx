import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CreateShopModal } from "./CreateShopModal";

const REGIONS = [{ id: 1, region_id: "N001", name: "North" }];

describe("CreateShopModal", () => {
  it("renders the OAuth connect step on open", () => {
    render(
      <CreateShopModal open onClose={() => {}} onCreated={() => {}} regions={REGIONS} />,
    );
    expect(screen.getByTestId("oauth-connect-button")).toBeInTheDocument();
  });
});
