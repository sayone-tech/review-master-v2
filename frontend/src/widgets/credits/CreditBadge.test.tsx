import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { CreditBadge } from "./CreditBadge";
import { resetCreditsStoreForTests, setShopCredits } from "./creditsStore";

const noop = () => undefined;

beforeEach(() => resetCreditsStoreForTests());

describe("CreditBadge", () => {
  it.each([
    [35, 100, "35 credits", "35 credits remaining this month"],
    [1, 100, "1 credit", "1 credit remaining this month"],
    [0, 100, "0 credits", "0 credits remaining this month"],
    [10000, 10000, "10,000 credits", "10,000 credits remaining this month"],
  ])("should show text, title and aria-label for %i of %i", (remaining, total, text, hint) => {
    render(<CreditBadge shopId={7} remaining={remaining} total={total} onOpen={noop} />);
    const badge = screen.getByRole("button", { name: hint });
    expect(badge).toHaveTextContent(text);
    expect(badge).toHaveAttribute("title", hint);
    expect(badge).toHaveAttribute("data-testid", "credits-badge-7");
    expect(badge.className).toContain("whitespace-nowrap");
  });

  it("should use the muted empty style for 0 credits when the shop is enabled", () => {
    render(<CreditBadge shopId={1} remaining={0} total={100} onOpen={noop} />);
    const badge = screen.getByTestId("credits-badge-1");
    expect(badge.className).toContain("bg-muted");
    expect(badge.className).toContain("text-white");
  });

  it("should say Not enabled with the explanatory label when total is 0", () => {
    render(<CreditBadge shopId={1} remaining={0} total={0} onOpen={noop} />);
    const hint = "Not enabled — AI replies aren't enabled for this shop";
    const badge = screen.getByRole("button", { name: hint });
    expect(badge).toHaveTextContent("Not enabled");
    expect(badge).toHaveAttribute("title", hint);
    expect(badge.className).toContain("bg-line-soft");
    expect(badge.className).toContain("text-muted");
  });

  it.each([
    [100, 100, "bg-green-tint"],
    [20, 100, "bg-amber-tint"],
    [3, 100, "bg-red-tint"],
  ])("should colour %i of %i with %s", (remaining, total, cls) => {
    render(<CreditBadge shopId={1} remaining={remaining} total={total} onOpen={noop} />);
    expect(screen.getByTestId("credits-badge-1").className).toContain(cls);
  });

  it("should use the dark green text on the green tint for AA contrast", () => {
    render(<CreditBadge shopId={1} remaining={50} total={100} onOpen={noop} />);
    expect(screen.getByTestId("credits-badge-1").className).toContain("text-[#166534]");
  });

  it.each([
    [null, null],
    [undefined, undefined],
    [35, null],
    [null, 100],
  ])("should render a non-interactive dash when credits are %s / %s", (remaining, total) => {
    render(<CreditBadge shopId={1} remaining={remaining} total={total} onOpen={noop} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    const dash = screen.getByText("—");
    expect(dash).not.toHaveAttribute("title");
  });

  it("should call onOpen when clicked", () => {
    const onOpen = vi.fn();
    render(<CreditBadge shopId={1} remaining={35} total={100} onOpen={onOpen} />);
    fireEvent.click(screen.getByTestId("credits-badge-1"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("should prefer the store entry for the shop over the row values", () => {
    setShopCredits(1, { remaining: 12, total: 100 });
    render(<CreditBadge shopId={1} remaining={35} total={100} onOpen={noop} />);
    expect(screen.getByTestId("credits-badge-1")).toHaveTextContent("12 credits");
  });

  it("should re-render when the store changes for its shop", () => {
    render(<CreditBadge shopId={1} remaining={35} total={100} onOpen={noop} />);
    act(() => setShopCredits(1, { remaining: 9, total: 100 }));
    expect(screen.getByTestId("credits-badge-1")).toHaveTextContent("9 credits");
  });
});
