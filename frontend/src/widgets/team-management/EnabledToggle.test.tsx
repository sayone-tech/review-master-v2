import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EnabledToggle } from "./EnabledToggle";

describe("EnabledToggle", () => {
  it("renders as ON when enabled=true", () => {
    render(
      <EnabledToggle
        enabled={true}
        memberName="Alice"
        onDisableRequest={vi.fn()}
        onEnableRequest={vi.fn()}
      />,
    );
    const btn = screen.getByRole("switch");
    expect(btn).toHaveAttribute("aria-checked", "true");
  });

  it("renders as OFF when enabled=false", () => {
    render(
      <EnabledToggle
        enabled={false}
        memberName="Alice"
        onDisableRequest={vi.fn()}
        onEnableRequest={vi.fn()}
      />,
    );
    const btn = screen.getByRole("switch");
    expect(btn).toHaveAttribute("aria-checked", "false");
  });

  it("click on ON state fires onDisableRequest", () => {
    const onDisable = vi.fn();
    render(
      <EnabledToggle
        enabled={true}
        memberName="Alice"
        onDisableRequest={onDisable}
        onEnableRequest={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(onDisable).toHaveBeenCalledOnce();
  });

  it("click on OFF state fires onEnableRequest", () => {
    const onEnable = vi.fn();
    render(
      <EnabledToggle
        enabled={false}
        memberName="Alice"
        onDisableRequest={vi.fn()}
        onEnableRequest={onEnable}
      />,
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(onEnable).toHaveBeenCalledOnce();
  });

  it("when disabled=true, click does nothing and aria-disabled is set", () => {
    const onDisable = vi.fn();
    const onEnable = vi.fn();
    render(
      <EnabledToggle
        enabled={true}
        disabled={true}
        disabledReason="You cannot disable yourself."
        memberName="Alice"
        onDisableRequest={onDisable}
        onEnableRequest={onEnable}
      />,
    );
    const btn = screen.getByRole("switch");
    fireEvent.click(btn);
    expect(onDisable).not.toHaveBeenCalled();
    expect(onEnable).not.toHaveBeenCalled();
    expect(btn).toHaveAttribute("aria-disabled", "true");
    expect(btn).toHaveAttribute("title", "You cannot disable yourself.");
  });
});
