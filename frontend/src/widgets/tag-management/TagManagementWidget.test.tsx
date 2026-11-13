import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TagManagementWidget } from "./TagManagementWidget";
import { useTagList } from "./useTagList";
import { setHeaderCount } from "../../shell/header";

vi.mock("./useTagList", () => ({ useTagList: vi.fn() }));
vi.mock("./useMergeProgress", () => ({
  useMergeProgress: () => ({ job: null, visible: false, dismiss: vi.fn(), kickoff: vi.fn() }),
}));
vi.mock("./MergeProgressBanner", () => ({ MergeProgressBanner: () => null }));
vi.mock("./TagMergeModal", () => ({ TagMergeModal: () => null }));
vi.mock("./TagTable", () => ({ TagTable: () => null }));
vi.mock("../../shell/header", () => ({ setHeaderCount: vi.fn() }));

function listState(over: Record<string, unknown> = {}) {
  return {
    rows: [],
    count: 0,
    loading: false,
    error: null,
    ordering: "-review_count",
    page: 1,
    pageSize: 25,
    totalPages: 1,
    hasNext: false,
    hasPrev: false,
    goNext: vi.fn(),
    goPrev: vi.fn(),
    toggleOrdering: vi.fn(),
    changePageSize: vi.fn(),
    setSearch: vi.fn(),
    refetch: vi.fn(),
    ...over,
  } as never;
}

beforeEach(() => vi.clearAllMocks());

describe("TagManagementWidget", () => {
  it("renders no page heading and reports the total to the header", () => {
    vi.mocked(useTagList).mockReturnValue(listState({ count: 1234 }));
    render(<TagManagementWidget />);
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(setHeaderCount).toHaveBeenLastCalledWith(1234);
  });

  it("hides the count during the first load", () => {
    vi.mocked(useTagList).mockReturnValue(listState({ loading: true }));
    render(<TagManagementWidget />);
    expect(setHeaderCount).toHaveBeenLastCalledWith(null);
  });
});
