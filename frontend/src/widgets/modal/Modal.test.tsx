import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal, ConfirmModal } from "./index";
import { emitToast } from "../../lib/toast";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal open={false} onClose={() => {}}>
        hidden
      </Modal>,
    );
    expect(screen.queryByTestId("modal-panel")).toBeNull();
  });

  it("renders title, body, close button when open", () => {
    render(
      <Modal open onClose={() => {}} title="Hello">
        <p>Body content</p>
      </Modal>,
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
    expect(screen.getByLabelText("Close")).toBeInTheDocument();
  });

  it("Escape key calls onClose", async () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose}>x</Modal>);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("Backdrop click calls onClose when dismissible", () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose}>x</Modal>);
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalled();
  });

  it("Click inside panel does NOT call onClose", () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose}>x</Modal>);
    fireEvent.click(screen.getByTestId("modal-panel"));
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("ConfirmModal", () => {
  it("renders amber icon and Cancel + confirm labels", () => {
    render(
      <ConfirmModal
        open
        onClose={() => {}}
        onConfirm={() => {}}
        variant="amber"
        title="Disable organisation?"
        message="This will hide the org."
        confirmLabel="Disable"
      />,
    );
    expect(screen.getByText("Disable organisation?")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-cancel")).toHaveTextContent("Cancel");
    expect(screen.getByTestId("confirm-confirm")).toHaveTextContent("Disable");
  });

  it("Confirm button gated by type-to-confirm match", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmModal
        open
        onClose={() => {}}
        onConfirm={onConfirm}
        variant="red"
        title="Delete?"
        message="This is permanent."
        confirmLabel="Delete"
        requireTypeToConfirm="AcmeCorp"
      />,
    );
    const btn = screen.getByTestId("confirm-confirm");
    expect(btn).toBeDisabled();
    const input = screen.getByTestId("type-to-confirm-input");
    await userEvent.type(input, "AcmeCorp");
    expect(btn).not.toBeDisabled();
  });
});

describe("emitToast", () => {
  afterEach(() => {
    // window event listeners cleanup handled by jsdom between tests
  });

  it("dispatches CustomEvent on window", () => {
    const listener = vi.fn();
    window.addEventListener("app:toast", listener);
    emitToast({ kind: "success", title: "Saved", msg: "" });
    expect(listener).toHaveBeenCalled();
    const call = listener.mock.calls[0][0] as CustomEvent;
    expect(call.detail).toEqual({ kind: "success", title: "Saved", msg: "" });
    window.removeEventListener("app:toast", listener);
  });
});
