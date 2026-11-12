import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OAuthConnectionSection } from "./OAuthConnectionSection";

// SHOP-22: permission note shown directly above the Google connect button.
describe("OAuthConnectionSection permission note", () => {
  function renderSection() {
    render(<OAuthConnectionSection onConnected={() => {}} onError={() => {}} />);
  }

  it("should describe the button with the permission note", () => {
    renderSection();
    const button = screen.getByRole("button", { name: /connect google business profile/i });
    const note = screen.getByTestId("oauth-permission-note");
    expect(button).toHaveAttribute("aria-describedby", note.id);
  });

  it("should place the permission note before the connect button", () => {
    renderSection();
    const button = screen.getByRole("button", { name: /connect google business profile/i });
    const note = screen.getByTestId("oauth-permission-note");
    expect(note.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("should list only what the app does with the business.manage permission", () => {
    renderSection();
    expect(
      screen.getByText("Google will ask for access to manage your Business Profile."),
    ).toBeInTheDocument();
    expect(screen.getByText("Read your reviews and your list of locations")).toBeInTheDocument();
    expect(
      screen.getByText("Post, edit or delete replies, only when you choose to"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("We never change your business details, hours, photos or ownership."),
    ).toBeInTheDocument();
  });

  it("should not promise that nothing is ever deleted, because users can delete replies", () => {
    renderSection();
    expect(screen.getByTestId("oauth-permission-note")).not.toHaveTextContent(/never .*delete/i);
  });
});
