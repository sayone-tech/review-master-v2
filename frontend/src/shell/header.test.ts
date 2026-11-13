import { beforeEach, describe, expect, it } from "vitest";
import { registerHeaderNavigation, setHeaderCount } from "./header";

const pill = () => document.getElementById("topbar-count")!;

beforeEach(() => {
  document.body.innerHTML = `<span id="topbar-count" hidden></span>
    <main id="main-content"></main>`;
});

describe("setHeaderCount", () => {
  it("shows the number in the pill", () => {
    setHeaderCount(42);
    expect(pill().hidden).toBe(false);
    expect(pill().textContent).toBe("42");
  });

  it("shows zero", () => {
    setHeaderCount(0);
    expect(pill().hidden).toBe(false);
    expect(pill().textContent).toBe("0");
  });

  it("formats thousands with toLocaleString", () => {
    setHeaderCount(1234);
    expect(pill().textContent).toBe((1234).toLocaleString());
  });

  it("hides and clears on null", () => {
    setHeaderCount(5);
    setHeaderCount(null);
    expect(pill().hidden).toBe(true);
    expect(pill().textContent).toBe("");
  });

  it("hides on a negative number", () => {
    setHeaderCount(5);
    setHeaderCount(-1);
    expect(pill().hidden).toBe(true);
  });

  it("does not throw when the pill is absent", () => {
    document.body.innerHTML = "";
    expect(() => setHeaderCount(3)).not.toThrow();
  });
});

describe("navigation", () => {
  beforeEach(() => {
    registerHeaderNavigation(document);
  });

  it("clears a count left by the previous page before the next page renders", () => {
    setHeaderCount(99);
    document.dispatchEvent(new Event("turbo:before-render"));
    expect(pill().hidden).toBe(true);
    expect(pill().textContent).toBe("");
  });

  it("reads data-page-count from #main-content on turbo:load", () => {
    document.getElementById("main-content")!.dataset.pageCount = "7";
    document.dispatchEvent(new Event("turbo:load"));
    expect(pill().hidden).toBe(false);
    expect(pill().textContent).toBe("7");
  });

  it("leaves a widget-set count alone on turbo:load when the page has no data-page-count", () => {
    setHeaderCount(12);
    document.dispatchEvent(new Event("turbo:load"));
    expect(pill().textContent).toBe("12");
  });

  it("ignores a non-numeric data-page-count", () => {
    document.getElementById("main-content")!.dataset.pageCount = "abc";
    document.dispatchEvent(new Event("turbo:load"));
    expect(pill().hidden).toBe(true);
  });
});
