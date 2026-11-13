import { useEffect, useMemo, useRef, useState } from "react";
import { Calendar, ChevronDown, Search, Star, Store, ThumbsUp } from "lucide-react";
import { FilterChips, FilterSearch, FilterSelect, MoreFiltersPanel, formatDateChip } from "../filters";
import type { FilterChip } from "../filters";
import type { ReviewFilterParams, ShopOption, TagOption } from "./types";

interface Props {
  shops: ShopOption[];
  filters: ReviewFilterParams;
  availableTags?: TagOption[];
  onChange: (next: ReviewFilterParams) => void;
}

interface PanelDraft {
  tags?: string[];
  from_date?: string;
  to_date?: string;
  is_replied?: boolean;
  has_comment?: boolean;
}

const PANEL_RESET: PanelDraft = {
  tags: undefined,
  from_date: undefined,
  to_date: undefined,
  is_replied: undefined,
  has_comment: undefined,
};

const SEARCH_DEBOUNCE_MS = 300;

const triSelectCls =
  "appearance-none w-full h-[34px] px-3 pr-8 text-[13px] text-ink bg-white border border-line rounded-[8px] outline-none cursor-pointer focus:border-ink";


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
    <div className="flex flex-col gap-[6px] min-w-0">
      <span className="text-[12px] font-semibold text-subtle">Tags</span>
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
            "relative w-full flex items-center justify-between gap-2 px-3 h-[34px] pr-8 text-[13px] font-normal text-ink bg-white border border-line rounded-[8px] outline-none cursor-pointer transition-[border-color,box-shadow] focus:border-ink focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]" +
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
          <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none" />
        </button>
        {open && (
          <div data-filter-popover>
          <div
            role="listbox"
            aria-multiselectable="true"
            aria-label="Tags"
            onKeyDown={onPanelKeyDown}
            className="absolute z-50 mt-1 left-0 right-0 bg-white border border-line rounded-[10px] shadow-md max-h-60 overflow-y-auto py-1"
          >
            <div className="px-2 py-2 border-b border-line">
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "#A1A1AA" }} aria-hidden="true" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(-1);
                  }}
                  placeholder="Search tags…"
                  className="w-full pl-9 pr-3 py-2 text-[14px] font-normal text-ink placeholder:text-faint bg-white border border-line rounded-[10px] transition-[border-color,box-shadow] focus:outline-none focus:border-ink focus:ring focus:ring-black/[0.05]"
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
          </div>
        )}
      </div>
    </div>
  );
}


function TriSelect({
  label,
  ariaLabel,
  value,
  onChange,
  options,
}: {
  label: string;
  ariaLabel: string;
  value: boolean | undefined;
  onChange: (v: boolean | undefined) => void;
  options: [string, string, string];
}) {
  return (
    <label className="flex flex-col gap-[6px] min-w-0">
      <span className="text-[12px] font-semibold text-subtle">{label}</span>
      <div className="relative">
        <select
          aria-label={ariaLabel}
          className={triSelectCls}
          value={value === undefined ? "" : value ? "true" : "false"}
          onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value === "true")}
        >
          <option value="">{options[0]}</option>
          <option value="true">{options[1]}</option>
          <option value="false">{options[2]}</option>
        </select>
        <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none" />
      </div>
    </label>
  );
}

export function ReviewFilters({ shops, filters, availableTags, onChange }: Props) {
  const [searchText, setSearchText] = useState(filters.search ?? "");
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // A typed-but-not-yet-applied search (debounce pending), else null.
  const pendingRef = useRef<string | null>(null);

  // External changes to the applied search (Clear all, empty-state clear, tag click) sync the
  // box and cancel any pending debounced apply of the old text.
  useEffect(() => {
    clearTimeout(timerRef.current);
    pendingRef.current = null;
    setSearchText(filters.search ?? "");
  }, [filters.search]);
  useEffect(() => () => clearTimeout(timerRef.current), []);

  // The parent replaced the filters with no search (e.g. the empty-state "Clear filters"): any
  // typed-but-unapplied search is stale too, so drop it.
  useEffect(() => {
    if (!filters.search && pendingRef.current !== null) {
      clearTimeout(timerRef.current);
      pendingRef.current = null;
      setSearchText("");
    }
  }, [filters]);

  // Any other change folds in a pending search so it is ONE request, not two.
  const apply = (patch: Partial<ReviewFilterParams>) => {
    const next = { ...filters, ...patch, page: 1 };
    if (pendingRef.current !== null && !("search" in patch)) {
      next.search = pendingRef.current || undefined;
    }
    clearTimeout(timerRef.current);
    pendingRef.current = null;
    onChange(next);
  };

  function handleSearch(v: string) {
    setSearchText(v);
    clearTimeout(timerRef.current);
    if (v === "") {
      apply({ search: undefined });
      return;
    }
    pendingRef.current = v;
    timerRef.current = setTimeout(() => {
      pendingRef.current = null;
      onChangeRef.current({ ...filtersRef.current, search: v, page: 1 });
    }, SEARCH_DEBOUNCE_MS);
  }

  function submitSearch() {
    clearTimeout(timerRef.current);
    pendingRef.current = null;
    if (searchText !== (filters.search ?? "")) apply({ search: searchText || undefined });
  }

  const tags = filters.tags ?? [];
  const dateChip = formatDateChip(filters.from_date, filters.to_date);
  const chips: FilterChip[] = [];
  if (filters.is_replied !== undefined)
    chips.push({
      key: "is_replied",
      label: filters.is_replied ? "Replied" : "Not replied",
      onRemove: () => apply({ is_replied: undefined }),
    });
  if (filters.has_comment !== undefined)
    chips.push({
      key: "has_comment",
      label: filters.has_comment ? "With comment" : "No comment",
      onRemove: () => apply({ has_comment: undefined }),
    });
  for (const tag of tags)
    chips.push({
      key: `tag:${tag}`,
      label: tag,
      onRemove: () => {
        const next = tags.filter((t) => t !== tag);
        apply({ tags: next.length ? next : undefined });
      },
    });
  if (dateChip)
    chips.push({
      key: "date",
      label: dateChip,
      onRemove: () => apply({ from_date: undefined, to_date: undefined }),
    });

  const activeCount =
    (tags.length ? 1 : 0) +
    (filters.from_date || filters.to_date ? 1 : 0) +
    (filters.is_replied !== undefined ? 1 : 0) +
    (filters.has_comment !== undefined ? 1 : 0);

  const applied: PanelDraft = {
    tags: filters.tags,
    from_date: filters.from_date,
    to_date: filters.to_date,
    is_replied: filters.is_replied,
    has_comment: filters.has_comment,
  };

  function clearAll() {
    clearTimeout(timerRef.current);
    pendingRef.current = null;
    setSearchText("");
    onChange({ page: 1 });
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <FilterSearch value={searchText} placeholder="Search reviews…" ariaLabel="Search reviews" onChange={handleSearch} onSubmit={submitSearch} />
        <FilterSelect<number>
          icon={Store}
          ariaLabel="Filter by store"
          placeholder="All stores"
          value={filters.shop}
          options={shops.map((s) => ({ value: s.id, label: s.name }))}
          onChange={(shop) => apply({ shop })}
        />
        <FilterSelect<number>
          icon={Star}
          ariaLabel="Filter by rating"
          placeholder="Any rating"
          value={filters.rating}
          options={[5, 4, 3, 2, 1].map((n) => ({ value: n, label: `${n} star${n === 1 ? "" : "s"}` }))}
          onChange={(rating) => apply({ rating: rating as ReviewFilterParams["rating"] })}
        />
        <FilterSelect<string>
          icon={ThumbsUp}
          ariaLabel="Filter by sentiment"
          placeholder="Any sentiment"
          value={filters.sentiment}
          options={[
            { value: "positive", label: "Positive" },
            { value: "neutral", label: "Neutral" },
            { value: "negative", label: "Negative" },
          ]}
          onChange={(sentiment) => apply({ sentiment: sentiment as ReviewFilterParams["sentiment"] })}
        />
        <MoreFiltersPanel<PanelDraft>
          applied={applied}
          activeCount={activeCount}
          onApply={(d) => apply({ ...d, tags: d.tags?.length ? d.tags : undefined })}
          onReset={() => apply(PANEL_RESET)}
        >
          {(draft, setDraft) => (
            <>
              <TagsFilter
                availableTags={availableTags}
                selected={draft.tags ?? []}
                onChange={(next) => setDraft({ ...draft, tags: next })}
              />
              <div className="flex flex-col gap-[6px] min-w-0">
                <span className="text-[12px] font-semibold text-subtle">Date range</span>
                <div className="flex items-center gap-2 px-3 h-[34px] border border-line rounded-[8px] bg-white focus-within:border-ink">
                  <Calendar size={14} className="text-subtle shrink-0" aria-hidden="true" />
                  <input
                    type="date"
                    aria-label="From date"
                    className="flex-1 bg-transparent focus:outline-none text-[13px] text-ink min-w-0"
                    value={draft.from_date ?? ""}
                    max={draft.to_date ?? undefined}
                    onChange={(e) => setDraft({ ...draft, from_date: e.target.value || undefined })}
                  />
                  <span className="text-faint shrink-0">—</span>
                  <input
                    type="date"
                    aria-label="To date"
                    className="flex-1 bg-transparent focus:outline-none text-[13px] text-ink min-w-0"
                    value={draft.to_date ?? ""}
                    min={draft.from_date ?? undefined}
                    onChange={(e) => setDraft({ ...draft, to_date: e.target.value || undefined })}
                  />
                </div>
              </div>
              <TriSelect
                label="Reply"
                ariaLabel="Filter by reply status"
                value={draft.is_replied}
                onChange={(v) => setDraft({ ...draft, is_replied: v })}
                options={["All replies", "Replied", "Not replied"]}
              />
              <TriSelect
                label="Comment"
                ariaLabel="Filter by comment presence"
                value={draft.has_comment}
                onChange={(v) => setDraft({ ...draft, has_comment: v })}
                options={["All comments", "With comment", "No comment"]}
              />
            </>
          )}
        </MoreFiltersPanel>
      </div>
      <FilterChips chips={chips} onClearAll={clearAll} />
    </div>
  );
}
