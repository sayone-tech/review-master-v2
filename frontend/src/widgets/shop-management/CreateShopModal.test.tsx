import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateShopModal } from "./CreateShopModal";
import * as api from "./api";
import { ApiError } from "./api";

const REGIONS = [{ id: 1, region_id: "N001", name: "North" }];

describe("CreateShopModal", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("Google selected by default", () => {
    render(
      <CreateShopModal open onClose={() => {}} onCreated={() => {}} regions={REGIONS} />,
    );
    const radio = screen.getByLabelText("Connect with Google") as HTMLInputElement;
    expect(radio.checked).toBe(true);
  });

  it("clicking Enter manually shows place_id and api_key fields", () => {
    render(
      <CreateShopModal open onClose={() => {}} onCreated={() => {}} regions={REGIONS} />,
    );
    fireEvent.click(screen.getByLabelText("Enter manually"));
    expect(screen.getByLabelText("Google Place ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Google Places API Key")).toBeInTheDocument();
  });

  it("renders place_id field error when API responds with field errors", async () => {
    vi.spyOn(api, "createShop").mockRejectedValue(
      new ApiError(400, { place_id: ["This Place ID was not found."] }),
    );
    render(
      <CreateShopModal open onClose={() => {}} onCreated={() => {}} regions={REGIONS} />,
    );
    fireEvent.click(screen.getByLabelText("Enter manually"));
    fireEvent.change(screen.getByLabelText("Shop Name"), { target: { value: "X" } });
    fireEvent.change(screen.getByLabelText("Google Place ID"), { target: { value: "ChIJ" } });
    fireEvent.change(screen.getByLabelText("Google Places API Key"), {
      target: { value: "AIza" },
    });
    fireEvent.submit(document.getElementById("create-shop-form")!);
    await waitFor(() =>
      expect(screen.getByText("This Place ID was not found.")).toBeInTheDocument(),
    );
  });

  it("renders non-field error at top when API responds with non_field_errors", async () => {
    vi.spyOn(api, "createShop").mockRejectedValue(
      new ApiError(400, {
        non_field_errors: [
          "Could not reach Google to verify this API key. Please try again.",
        ],
      }),
    );
    render(
      <CreateShopModal open onClose={() => {}} onCreated={() => {}} regions={REGIONS} />,
    );
    fireEvent.click(screen.getByLabelText("Enter manually"));
    fireEvent.change(screen.getByLabelText("Shop Name"), { target: { value: "X" } });
    fireEvent.change(screen.getByLabelText("Google Place ID"), { target: { value: "ChIJ" } });
    fireEvent.change(screen.getByLabelText("Google Places API Key"), {
      target: { value: "AIza" },
    });
    fireEvent.submit(document.getElementById("create-shop-form")!);
    await waitFor(() =>
      expect(screen.getByTestId("non-field-error")).toBeInTheDocument(),
    );
  });
});
