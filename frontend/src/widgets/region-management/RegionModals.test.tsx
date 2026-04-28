import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CreateRegionModal } from "./CreateRegionModal";

describe("CreateRegionModal — auto-ID mechanic (RGN-04 / RGN-05)", () => {
  it("populates Region ID from Region Name as user types", () => {
    render(
      <CreateRegionModal open={true} regionCount={3} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(nameInput, { target: { value: "North West" } });
    expect(idInput).toHaveValue("NW004");
    expect(idInput).toHaveAttribute("data-auto-mode", "true");
  });

  it("stops auto-population when Region ID is manually edited", () => {
    render(
      <CreateRegionModal open={true} regionCount={0} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(idInput, { target: { value: "MANUAL1" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "false");
    fireEvent.change(nameInput, { target: { value: "North East" } });
    expect(idInput).toHaveValue("MANUAL1"); // not overwritten
  });

  it("resumes auto-population when Region ID is cleared (RGN-05)", () => {
    render(
      <CreateRegionModal open={true} regionCount={0} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(idInput, { target: { value: "MANUAL1" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "false");
    fireEvent.change(idInput, { target: { value: "" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "true");
    fireEvent.change(nameInput, { target: { value: "South East" } });
    expect(idInput).toHaveValue("SE001");
  });
});

describe("EditRegionModal — no auto-ID in edit mode (RGN-08)", () => {
  it("typing in Region Name does not update Region ID in edit mode", async () => {
    const { EditRegionModal } = await import("./EditRegionModal");
    const region = { id: 1, name: "Old Name", region_id: "OLD001", created_at: "" };
    render(
      <EditRegionModal open={true} region={region} onClose={() => {}} onUpdated={() => {}} />,
    );
    const nameInput = screen.getByDisplayValue("Old Name");
    const idInput = screen.getByDisplayValue("OLD001");
    fireEvent.change(nameInput, { target: { value: "New Name Changed" } });
    expect(idInput).toHaveValue("OLD001"); // Region ID unchanged
  });
});
