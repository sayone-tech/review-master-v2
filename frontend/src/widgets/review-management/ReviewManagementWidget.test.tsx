import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewManagementWidget } from "./ReviewManagementWidget";
import { useReviews } from "./useReviews";
import { setHeaderCount } from "../../shell/header";

vi.mock("./useReviews", () => ({ useReviews: vi.fn() }));
vi.mock("./api", () => ({
  fetchReviewStats: vi.fn().mockResolvedValue(null),
  fetchTagList: vi.fn().mockResolvedValue([]),
}));
vi.mock("./ReviewEmptyStates", () => ({
  ReviewEmptyStates: { EmptyStateA: () => null, EmptyStateB: () => null, EmptyStateC: () => null },
}));
vi.mock("./ReviewFilters", () => ({ ReviewFilters: () => null }));
vi.mock("./ReviewStatsCards", () => ({ ReviewStatsCards: () => null }));
vi.mock("./ReviewTable", () => ({ ReviewTable: () => null }));
vi.mock("../../shell/header", () => ({ setHeaderCount: vi.fn() }));

function reviewsState(over: Record<string, unknown> = {}) {
  return {
    rows: [],
    count: 0,
    next: null,
    previous: null,
    loading: false,
    filters: {},
    currentPage: 1,
    totalPages: 1,
    applyFilters: vi.fn(),
    clearFilters: vi.fn(),
    setOrdering: vi.fn(),
    setPageSize: vi.fn(),
    goToPage: vi.fn(),
    goNext: vi.fn(),
    goPrev: vi.fn(),
    replaceRow: vi.fn(),
    ...over,
  } as never;
}

beforeEach(() => vi.clearAllMocks());

describe("ReviewManagementWidget", () => {
  it("renders no page heading and reports the review total to the header", () => {
    vi.mocked(useReviews).mockReturnValue(reviewsState({ count: 1234 }));
    render(
      <ReviewManagementWidget
        userRole="ORG_ADMIN"
        openProgressShopId={null}
        initialShops={[]}
        hasConnectedShops
      />,
    );
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(setHeaderCount).toHaveBeenLastCalledWith(1234);
  });

  it("clears the header count on unmount", () => {
    vi.mocked(useReviews).mockReturnValue(reviewsState({ count: 5 }));
    const { unmount } = render(
      <ReviewManagementWidget userRole="STAFF_ADMIN" openProgressShopId={null} initialShops={[]} />,
    );
    unmount();
    expect(setHeaderCount).toHaveBeenLastCalledWith(null);
  });
});
