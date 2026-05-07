import { useState } from "react";
import { Calendar, Search, SlidersHorizontal, X } from "lucide-react";
import type { ReviewFilterParams, ShopOption } from "./types";

const selectCls =
  "px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

interface DraftFilters {
  search: string;
  shop?: number;
  rating?: 1 | 2 | 3 | 4 | 5;
  sentiment?: "positive" | "neutral" | "negative";
  is_replied?: boolean;
  has_comment?: boolean;
  from_date?: string;
  to_date?: string;
}

interface Props {
  shops: ShopOption[];
  filters: ReviewFilterParams;
  onApply: (draft: DraftFilters) => void;
  onReset: () => void;
}

export function ReviewFilters({ shops, filters, onApply, onReset }: Props) {
  const [draft, setDraft] = useState<DraftFilters>({
    search: filters.search ?? "",
    shop: filters.shop,
    rating: filters.rating,
    sentiment: filters.sentiment,
    is_replied: filters.is_replied,
    has_comment: filters.has_comment,
    from_date: filters.from_date,
    to_date: filters.to_date,
  });

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.rating !== undefined ||
      filters.sentiment ||
      filters.is_replied !== undefined ||
      filters.has_comment !== undefined ||
      filters.from_date ||
      filters.to_date,
  );

  const handleReset = () => {
    setDraft({
      search: "",
      shop: undefined,
      rating: undefined,
      sentiment: undefined,
      is_replied: undefined,
      has_comment: undefined,
      from_date: undefined,
      to_date: undefined,
    });
    onReset();
  };

  return (
    <div className="space-y-2">
      {/* Row 1 — search + the three "any …" selects (each flex-1 fills the row) */}
      <div className="flex flex-wrap items-stretch gap-2">
        {/* Search — wider weight */}
        <div className="flex items-center gap-2 px-3 py-2 bg-white border border-line rounded-md flex-[2] min-w-[220px] focus-within:border-ink focus-within:ring focus-within:ring-black/[0.06]">
          <Search size={14} className="text-muted shrink-0" aria-hidden="true" />
          <input
            type="text"
            className="flex-1 min-w-0 bg-transparent focus:outline-none text-[13.5px]"
            placeholder="Search reviews…"
            value={draft.search}
            onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
            aria-label="Search reviews"
          />
        </div>

        {/* Store */}
        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.shop ?? ""}
          onChange={(e) =>
            setDraft((d) => ({ ...d, shop: e.target.value ? Number(e.target.value) : undefined }))
          }
          aria-label="Filter by store"
        >
          <option value="">All Stores</option>
          {shops.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        {/* Rating */}
        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.rating ?? ""}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              rating: e.target.value ? (Number(e.target.value) as 1 | 2 | 3 | 4 | 5) : undefined,
            }))
          }
          aria-label="Filter by rating"
        >
          <option value="">Any Rating</option>
          <option value="5">★★★★★ 5 stars</option>
          <option value="4">★★★★☆ 4 stars</option>
          <option value="3">★★★☆☆ 3 stars</option>
          <option value="2">★★☆☆☆ 2 stars</option>
          <option value="1">★☆☆☆☆ 1 star</option>
        </select>

        {/* Sentiment */}
        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.sentiment ?? ""}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              sentiment: e.target.value
                ? (e.target.value as "positive" | "neutral" | "negative")
                : undefined,
            }))
          }
          aria-label="Filter by sentiment"
        >
          <option value="">Any Sentiment</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
        </select>
      </div>

      {/* Row 2 — date range + replies + comments + action buttons */}
      <div className="flex flex-wrap items-stretch gap-2">
        {/* Date range */}
        <div className="flex items-center gap-1 px-3 bg-white border border-line rounded-md text-[13.5px] flex-[2] min-w-[260px]">
          <Calendar size={13} className="text-muted shrink-0" aria-hidden="true" />
          <input
            type="date"
            className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
            value={draft.from_date ?? ""}
            max={draft.to_date ?? undefined}
            onChange={(e) => setDraft((d) => ({ ...d, from_date: e.target.value || undefined }))}
            aria-label="From date"
          />
          <span className="text-muted px-0.5">–</span>
          <input
            type="date"
            className="flex-1 bg-transparent focus:outline-none text-[13px] min-w-0 py-2"
            value={draft.to_date ?? ""}
            min={draft.from_date ?? undefined}
            onChange={(e) => setDraft((d) => ({ ...d, to_date: e.target.value || undefined }))}
            aria-label="To date"
          />
        </div>

        {/* Reply status */}
        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.is_replied === undefined ? "" : draft.is_replied ? "true" : "false"}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              is_replied: e.target.value === "" ? undefined : e.target.value === "true",
            }))
          }
          aria-label="Filter by reply status"
        >
          <option value="">All Replies</option>
          <option value="true">Replied</option>
          <option value="false">Not Replied</option>
        </select>

        {/* Comment presence */}
        <select
          className={`${selectCls} flex-1 min-w-[140px]`}
          value={draft.has_comment === undefined ? "" : draft.has_comment ? "true" : "false"}
          onChange={(e) =>
            setDraft((d) => ({
              ...d,
              has_comment: e.target.value === "" ? undefined : e.target.value === "true",
            }))
          }
          aria-label="Filter by comment presence"
        >
          <option value="">All Comments</option>
          <option value="true">With Comment</option>
          <option value="false">No Comment</option>
        </select>

        {/* Filter button */}
        <button
          type="button"
          onClick={() => onApply(draft)}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-black text-yellow text-[13.5px] font-semibold rounded-md hover:bg-ink/90 shrink-0"
        >
          <SlidersHorizontal size={13} aria-hidden="true" />
          Filter
        </button>

        {/* Reset — only when active filters */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-[13.5px] text-muted hover:text-ink border border-line rounded-md bg-white shrink-0"
          >
            <X size={13} aria-hidden="true" />
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
