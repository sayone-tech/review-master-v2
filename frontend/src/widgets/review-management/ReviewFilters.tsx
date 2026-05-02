import { useState } from "react";
import type { ReviewFilterParams, ShopOption, SortKey } from "./types";

const inputCls =
  "px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

interface Props {
  shops: ShopOption[];
  filters: ReviewFilterParams;
  totalCount: number;
  pageStart: number;
  pageEnd: number;
  onSearch: (s: string) => void;
  onShop: (s?: number) => void;
  onRating: (r?: 1 | 2 | 3 | 4 | 5) => void;
  onSentiment: (s?: "positive" | "neutral" | "negative") => void;
  onIsReplied: (r?: boolean) => void;
  onFromDate: (d?: string) => void;
  onToDate: (d?: string) => void;
  onOrdering: (o: SortKey) => void;
  onClearAll: () => void;
}

export function ReviewFilters(props: Props) {
  const {
    shops,
    filters,
    totalCount,
    pageStart,
    pageEnd,
    onSearch,
    onShop,
    onRating,
    onSentiment,
    onIsReplied,
    onFromDate,
    onToDate,
    onOrdering,
    onClearAll,
  } = props;
  const [searchInput, setSearchInput] = useState(filters.search ?? "");

  const activeChips: { label: string; onRemove: () => void }[] = [];
  if (filters.shop !== undefined) {
    const name = shops.find((s) => s.id === filters.shop)?.name ?? `Shop ${filters.shop}`;
    activeChips.push({ label: `Shop: ${name}`, onRemove: () => onShop(undefined) });
  }
  if (filters.rating !== undefined) {
    activeChips.push({ label: `${filters.rating} stars`, onRemove: () => onRating(undefined) });
  }
  if (filters.sentiment) {
    activeChips.push({
      label: `Sentiment: ${filters.sentiment}`,
      onRemove: () => onSentiment(undefined),
    });
  }
  if (filters.is_replied !== undefined) {
    activeChips.push({
      label: filters.is_replied ? "Replied" : "Not Replied",
      onRemove: () => onIsReplied(undefined),
    });
  }
  if (filters.from_date) {
    activeChips.push({ label: `From: ${filters.from_date}`, onRemove: () => onFromDate(undefined) });
  }
  if (filters.to_date) {
    activeChips.push({ label: `To: ${filters.to_date}`, onRemove: () => onToDate(undefined) });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          className={`${inputCls} flex-1 min-w-[200px]`}
          placeholder="Search reviews…"
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            onSearch(e.target.value);
          }}
          aria-label="Search reviews"
        />
        <select
          className={inputCls}
          value={filters.shop ?? ""}
          onChange={(e) => onShop(e.target.value ? Number(e.target.value) : undefined)}
          aria-label="Filter by store"
        >
          <option value="">All Stores</option>
          {shops.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          className={inputCls}
          value={filters.rating ?? ""}
          onChange={(e) =>
            onRating(e.target.value ? (Number(e.target.value) as 1 | 2 | 3 | 4 | 5) : undefined)
          }
          aria-label="Filter by rating"
        >
          <option value="">Any Rating</option>
          <option value="5">5 stars</option>
          <option value="4">4 stars</option>
          <option value="3">3 stars</option>
          <option value="2">2 stars</option>
          <option value="1">1 star</option>
        </select>
        <select
          className={inputCls}
          value={filters.sentiment ?? ""}
          onChange={(e) =>
            onSentiment(
              e.target.value
                ? (e.target.value as "positive" | "neutral" | "negative")
                : undefined,
            )
          }
          aria-label="Filter by sentiment"
        >
          <option value="">Any Sentiment</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
        </select>
        <select
          className={inputCls}
          value={filters.is_replied === undefined ? "" : filters.is_replied ? "true" : "false"}
          onChange={(e) =>
            onIsReplied(e.target.value === "" ? undefined : e.target.value === "true")
          }
          aria-label="Filter by reply status"
        >
          <option value="">All</option>
          <option value="true">Replied</option>
          <option value="false">Not Replied</option>
        </select>
        <label className="flex items-center gap-1 text-[12px] text-muted">
          From
          <input
            type="date"
            className={inputCls}
            value={filters.from_date ?? ""}
            onChange={(e) => onFromDate(e.target.value || undefined)}
            aria-label="From date"
          />
        </label>
        <label className="flex items-center gap-1 text-[12px] text-muted">
          To
          <input
            type="date"
            className={inputCls}
            value={filters.to_date ?? ""}
            onChange={(e) => onToDate(e.target.value || undefined)}
            aria-label="To date"
          />
        </label>
      </div>
      {activeChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {activeChips.map((c) => (
            <span
              key={c.label}
              className="inline-flex items-center gap-1 px-2 py-1 bg-line-soft text-ink text-[12px] rounded-full"
            >
              {c.label}
              <button
                type="button"
                className="text-muted hover:text-red"
                onClick={c.onRemove}
                aria-label={`Remove ${c.label} filter`}
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            className="text-[12px] text-muted underline hover:text-ink"
            onClick={onClearAll}
          >
            Clear all
          </button>
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className="text-[14px] text-muted">
          Showing {totalCount === 0 ? 0 : pageStart}-{pageEnd} of {totalCount} reviews
        </span>
        <select
          className={inputCls}
          value={filters.ordering ?? "-review_create_time"}
          onChange={(e) => onOrdering(e.target.value as SortKey)}
          aria-label="Sort order"
        >
          <option value="-review_create_time">Newest first</option>
          <option value="review_create_time">Oldest first</option>
          <option value="-star_rating">Highest rating</option>
          <option value="star_rating">Lowest rating</option>
        </select>
      </div>
    </div>
  );
}
