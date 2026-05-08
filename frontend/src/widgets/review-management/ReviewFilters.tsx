import { useState } from "react";
import { Calendar, MessageSquare, RefreshCw, Search, Star, Tag, ThumbsUp } from "lucide-react";
import type { ReviewFilterParams, ShopOption } from "./types";

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

const selectCls =
  "appearance-none w-full px-3.5 py-[10px] pr-9 text-[14px] font-medium text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

function ChevronIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function FilterLabel({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium text-subtle uppercase tracking-[0.05em]">
      <span className="text-muted">{icon}</span>
      <span>{label}</span>
    </span>
  );
}

function StoreIcon({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9l1-4h16l1 4" />
      <path d="M3 9v11h18V9" />
      <path d="M9 9v11" />
      <path d="M15 9v11" />
    </svg>
  );
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
    <div className="bg-white border border-line rounded-xl p-3.5 mb-[18px]">
      {/* Row 1 — search + store + rating + sentiment + actions */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) auto",
          gap: 14,
          alignItems: "end",
        }}
      >
        {/* Search */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Search size={15} />} label="Search" />
          <div className="flex items-center gap-2 px-3.5 py-[10px] bg-white border border-line rounded-[10px] transition-[border-color,box-shadow] hover:border-[#D4D4D8] focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]">
            <Search size={14} className="text-muted shrink-0" aria-hidden="true" />
            <input
              type="text"
              className="flex-1 min-w-0 bg-transparent focus:outline-none text-[14px] font-medium text-ink placeholder:text-faint placeholder:font-normal"
              placeholder="Search reviews…"
              value={draft.search}
              onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
              aria-label="Search reviews"
            />
          </div>
        </label>

        {/* Store */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<StoreIcon size={15} />} label="Store" />
          <div className="relative">
            <select
              aria-label="Filter by store"
              className={selectCls}
              value={draft.shop ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  shop: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            >
              <option value="">All stores</option>
              {shops.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Rating */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Star size={15} />} label="Rating" />
          <div className="relative">
            <select
              aria-label="Filter by rating"
              className={selectCls}
              value={draft.rating ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  rating: e.target.value
                    ? (Number(e.target.value) as 1 | 2 | 3 | 4 | 5)
                    : undefined,
                }))
              }
            >
              <option value="">Any rating</option>
              <option value="5">★★★★★ 5 stars</option>
              <option value="4">★★★★☆ 4 stars</option>
              <option value="3">★★★☆☆ 3 stars</option>
              <option value="2">★★☆☆☆ 2 stars</option>
              <option value="1">★☆☆☆☆ 1 star</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Sentiment */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<ThumbsUp size={15} />} label="Sentiment" />
          <div className="relative">
            <select
              aria-label="Filter by sentiment"
              className={selectCls}
              value={draft.sentiment ?? ""}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  sentiment: e.target.value
                    ? (e.target.value as "positive" | "neutral" | "negative")
                    : undefined,
                }))
              }
            >
              <option value="">Any sentiment</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Actions */}
        <div className="flex items-center gap-2 pb-0">
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 px-3 py-[10px] rounded-[10px] bg-transparent border border-dashed border-line text-subtle text-[13px] hover:text-ink hover:border-ink transition-colors"
            >
              <RefreshCw size={13} aria-hidden="true" />
              Reset
            </button>
          )}
          <button
            type="button"
            onClick={() => onApply(draft)}
            className="inline-flex items-center gap-1.5 px-3.5 py-[10px] rounded-[10px] bg-yellow text-black border border-yellow-hover text-[14px] font-medium hover:bg-yellow-hover transition-colors shrink-0"
          >
            Apply
          </button>
        </div>
      </div>

      {/* Row 2 — date range + reply + comment */}
      <div
        className="mt-3 pt-3 border-t border-dashed border-line"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr)",
          gap: 14,
          alignItems: "end",
        }}
      >
        {/* Date range — two date inputs side by side */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Calendar size={15} />} label="Date range" />
          <div className="flex items-center gap-2 px-3.5 py-[10px] border border-line rounded-[10px] bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(10,10,10,0.05)] transition-[border-color,box-shadow]">
            <Calendar size={14} className="text-subtle shrink-0" aria-hidden="true" />
            <input
              type="date"
              aria-label="From date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.from_date ?? ""}
              max={draft.to_date ?? undefined}
              onChange={(e) =>
                setDraft((d) => ({ ...d, from_date: e.target.value || undefined }))
              }
            />
            <span className="text-faint font-medium shrink-0">—</span>
            <input
              type="date"
              aria-label="To date"
              className="flex-1 bg-transparent focus:outline-none text-[14px] text-ink min-w-0"
              value={draft.to_date ?? ""}
              min={draft.from_date ?? undefined}
              onChange={(e) =>
                setDraft((d) => ({ ...d, to_date: e.target.value || undefined }))
              }
            />
          </div>
        </label>

        {/* Reply status */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<MessageSquare size={15} />} label="Reply" />
          <div className="relative">
            <select
              aria-label="Filter by reply status"
              className={selectCls}
              value={
                draft.is_replied === undefined ? "" : draft.is_replied ? "true" : "false"
              }
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  is_replied:
                    e.target.value === "" ? undefined : e.target.value === "true",
                }))
              }
            >
              <option value="">All replies</option>
              <option value="true">Replied</option>
              <option value="false">Not replied</option>
            </select>
            <ChevronIcon />
          </div>
        </label>

        {/* Comment presence */}
        <label className="flex flex-col gap-1.5 min-w-0">
          <FilterLabel icon={<Tag size={15} />} label="Comment" />
          <div className="relative">
            <select
              aria-label="Filter by comment presence"
              className={selectCls}
              value={
                draft.has_comment === undefined ? "" : draft.has_comment ? "true" : "false"
              }
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  has_comment:
                    e.target.value === "" ? undefined : e.target.value === "true",
                }))
              }
            >
              <option value="">All comments</option>
              <option value="true">With comment</option>
              <option value="false">No comment</option>
            </select>
            <ChevronIcon />
          </div>
        </label>
      </div>
    </div>
  );
}
