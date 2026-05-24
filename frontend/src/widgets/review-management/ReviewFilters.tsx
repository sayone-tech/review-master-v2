import { useEffect, useMemo, useRef, useState } from "react";
import { Calendar, MessageSquare, RefreshCw, Search, Star, Tag, ThumbsUp } from "lucide-react";
import type { ReviewFilterParams, ShopOption, TagOption } from "./types";

interface DraftFilters {
  search: string;
  shop?: number;
  rating?: 1 | 2 | 3 | 4 | 5;
  sentiment?: "positive" | "neutral" | "negative";
  is_replied?: boolean;
  has_comment?: boolean;
  from_date?: string;
  to_date?: string;
  tags?: string[];
}

interface Props {
  shops: ShopOption[];
  filters: ReviewFilterParams;
  onApply: (draft: DraftFilters) => void;
  onReset: () => void;
  availableTags?: TagOption[];
}

const selectCls =
  "appearance-none w-full px-4 py-2 pr-9 text-[14px] font-normal text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]";

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
    <span className="inline-flex items-center gap-2 text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
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

interface TagsFilterProps {
  availableTags?: TagOption[];
  selected: string[];
  onChange: (next: string[]) => void;
}

function TagsFilter({ availableTags, selected, onChange }: TagsFilterProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const loading = availableTags === undefined;
  const trimmedQuery = query.trim();
  const hasMinChars = trimmedQuery.length >= 2;
  const filtered = useMemo(() => {
    if (!hasMinChars) return [];
    const q = trimmedQuery.toLowerCase();
    return (availableTags ?? []).filter((t) => t.label.toLowerCase().includes(q));
  }, [availableTags, trimmedQuery, hasMinChars]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  // Focus search input on open
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => searchInputRef.current?.focus());
    } else {
      setActiveIndex(-1);
    }
  }, [open]);

  const triggerLabel = (() => {
    if (selected.length === 0) return "Any tag";
    if (selected.length === 1) return selected[0];
    return `${selected.length} tags`;
  })();

  const toggleLabel = (label: string) => {
    if (selected.includes(label)) {
      onChange(selected.filter((l) => l !== label));
    } else {
      onChange([...selected, label]);
    }
  };

  const onTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (loading) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen((o) => !o);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
      setQuery("");
    }
  };

  const onPanelKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setQuery("");
      triggerRef.current?.focus();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (filtered.length === 0 ? -1 : Math.min(filtered.length - 1, i + 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (filtered.length === 0 ? -1 : Math.max(0, i - 1)));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < filtered.length) {
        e.preventDefault();
        toggleLabel(filtered[activeIndex].label);
      }
    } else if (e.key === "Tab") {
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <label className="flex flex-col gap-2 min-w-0">
      <FilterLabel icon={<Tag size={15} />} label="Tags" />
      <div className="relative" ref={containerRef}>
        <button
          ref={triggerRef}
          type="button"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Filter by tag"
          disabled={loading}
          onClick={() => !loading && setOpen((o) => !o)}
          onKeyDown={onTriggerKeyDown}
          className={
            "w-full flex items-center justify-between gap-2 px-4 py-2 pr-9 text-[14px] font-normal text-ink bg-white border border-line rounded-[10px] outline-none cursor-pointer transition-[border-color,box-shadow] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]" +
            (loading ? " opacity-50 cursor-not-allowed pointer-events-none" : "")
          }
        >
          <span className="flex items-center gap-2 min-w-0">
            <span className="truncate">{triggerLabel}</span>
            {selected.length > 0 && (
              <span
                className="inline-flex items-center justify-center w-4 h-4 bg-yellow text-black text-[10px] font-semibold rounded-full shrink-0"
                aria-hidden="true"
              >
                {selected.length}
              </span>
            )}
          </span>
          <ChevronIcon />
        </button>
        {open && (
          <div
            role="listbox"
            aria-multiselectable="true"
            aria-label="Tags"
            onKeyDown={onPanelKeyDown}
            className="absolute z-50 mt-1 left-0 right-0 bg-white border border-line rounded-[10px] shadow-md max-h-60 overflow-y-auto py-1"
          >
            <div className="px-2 py-2 border-b border-line">
              <div className="flex items-center gap-2 px-3 py-2 bg-white border border-line rounded-[10px] transition-[border-color,box-shadow] focus-within:ring-2 focus-within:ring-yellow">
                <Search size={13} className="text-muted shrink-0" aria-hidden="true" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(-1);
                  }}
                  placeholder="Search tags…"
                  className="flex-1 min-w-0 text-[14px] font-normal text-ink placeholder:text-faint focus:outline-none bg-transparent"
                  aria-label="Search tags"
                />
              </div>
            </div>
            {!hasMinChars ? (
              <div className="px-3 py-3 text-[12px] text-muted">
                Type at least 2 characters to search tags
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-3 text-[12px] text-muted">
                {`No tags match "${trimmedQuery}"`}
              </div>
            ) : (
              filtered.map((opt, idx) => {
                const isSelected = selected.includes(opt.label);
                const isActive = idx === activeIndex;
                return (
                  <div
                    key={opt.label}
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={(e) => {
                      e.preventDefault();
                      toggleLabel(opt.label);
                    }}
                    className={
                      "flex items-center justify-between px-3 py-2 cursor-pointer transition-colors " +
                      (isSelected || isActive ? "bg-line-soft" : "hover:bg-line-soft")
                    }
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <span
                        className="inline-flex items-center justify-center w-3 text-[12px] text-ink shrink-0"
                        aria-hidden="true"
                      >
                        {isSelected ? "✓" : ""}
                      </span>
                      <span className="text-[13px] font-semibold text-ink truncate">
                        {opt.label}
                      </span>
                    </span>
                    <span className="text-[11px] text-faint shrink-0">{opt.count}</span>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </label>
  );
}

export function ReviewFilters({ shops, filters, onApply, onReset, availableTags }: Props) {
  const [draft, setDraft] = useState<DraftFilters>({
    search: filters.search ?? "",
    shop: filters.shop,
    rating: filters.rating,
    sentiment: filters.sentiment,
    is_replied: filters.is_replied,
    has_comment: filters.has_comment,
    from_date: filters.from_date,
    to_date: filters.to_date,
    tags: filters.tags ?? [],
  });

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.shop !== undefined ||
      filters.rating !== undefined ||
      filters.sentiment ||
      filters.is_replied !== undefined ||
      filters.has_comment !== undefined ||
      filters.from_date ||
      filters.to_date ||
      (filters.tags && filters.tags.length > 0),
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
      tags: [],
    });
    onReset();
  };

  return (
    <div className="bg-white border border-line rounded-xl p-4 mb-4">
      {/* Row 1 — search + store + rating + sentiment */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)",
          gap: 16,
          alignItems: "end",
        }}
      >
        {/* Search */}
        <label className="flex flex-col gap-2 min-w-0">
          <FilterLabel icon={<Search size={15} />} label="Search" />
          <div className="flex items-center gap-2 px-4 py-2 bg-white border border-line rounded-[10px] transition-[border-color,box-shadow] focus-within:ring-2 focus-within:ring-yellow">
            <Search size={14} className="text-muted shrink-0" aria-hidden="true" />
            <input
              type="text"
              className="flex-1 min-w-0 bg-transparent focus:outline-none text-[14px] font-normal text-ink placeholder:text-faint"
              placeholder="Search reviews…"
              value={draft.search}
              onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
              aria-label="Search reviews"
            />
          </div>
        </label>

        {/* Store */}
        <label className="flex flex-col gap-2 min-w-0">
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

        {/* Tags multi-select — placed after Store because the inline search
           input makes this control visually heavier than a plain <select>;
           grouping it next to Store keeps the heavier "entity" filters
           together and the lighter scalar filters (Rating, Sentiment) to
           the right. */}
        <TagsFilter
          availableTags={availableTags}
          selected={draft.tags ?? []}
          onChange={(next) => setDraft((d) => ({ ...d, tags: next }))}
        />

        {/* Rating */}
        <label className="flex flex-col gap-2 min-w-0">
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
        <label className="flex flex-col gap-2 min-w-0">
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

      </div>

      {/* Row 2 — date range + reply + comment + actions */}
      <div
        className="mt-3 pt-3 border-t border-dashed border-line"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) auto",
          gap: 16,
          alignItems: "end",
        }}
      >
        {/* Date range — two date inputs side by side */}
        <label className="flex flex-col gap-2 min-w-0">
          <FilterLabel icon={<Calendar size={15} />} label="Date range" />
          <div className="flex items-center gap-2 px-4 py-2 border border-line rounded-[10px] bg-white focus-within:ring-2 focus-within:ring-yellow transition-[border-color,box-shadow]">
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
            <span className="text-faint font-normal shrink-0">—</span>
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
        <label className="flex flex-col gap-2 min-w-0">
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
        <label className="flex flex-col gap-2 min-w-0">
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

        {/* Actions */}
        <div className="flex items-center gap-2">
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-[10px] bg-transparent border border-dashed border-line text-subtle text-[14px] hover:text-ink hover:border-ink transition-colors"
            >
              <RefreshCw size={13} aria-hidden="true" />
              Reset
            </button>
          )}
          <button
            type="button"
            onClick={() => onApply(draft)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-[10px] bg-yellow text-black border border-yellow-hover text-[14px] font-semibold hover:bg-yellow-hover transition-colors shrink-0"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
