// Phase 18 Plan 04 — DuplicatePickerModal
//
// Detail-view entry point for marking an action item as a duplicate of another.
// Renders a debounced (300ms) search list of eligible primaries — same-scope
// AI items in the caller's organisation. Selecting one fires onPicked with the
// picked primary; the parent (ActionItemModal) then opens a ConfirmModal to
// finalise the merge.
//
// The list endpoint already filters out canonical/duplicate items
// (canonical__isnull=True, applied in plan 18-02), so any returned row is a
// valid primary candidate. We additionally exclude the current item itself
// and anything where source !== "AI" client-side as a belt-and-braces guard.
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Modal } from "../modal/Modal";
import { listActionItems } from "./api";
import type { ActionItemDetail, ActionItemListRow, ListParams } from "./types";

interface Props {
  open: boolean;
  currentItem: ActionItemDetail;
  onClose: () => void;
  onPicked: (primaryId: number, primaryItem: ActionItemListRow) => void;
}

export function DuplicatePickerModal({ open, currentItem, onClose, onPicked }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ActionItemListRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Reset state whenever the modal opens/closes.
  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
      setSelectedId(null);
      setLoading(false);
    }
  }, [open]);

  // Debounced fetch of candidate primaries.
  //
  // Phase 18 (WR-06 fix): for SHOP-scope items, restrict the picker to
  // candidates in the same shop. The backend allows cross-shop merges
  // within the same org/scope (D-05 only constrains scope, not shop), but
  // the resulting "Also reported in" UI is semantically confusing if a
  // Shop A item suddenly has a duplicate whose source review came from
  // Shop B. Same-shop is the use-case CONTEXT.md describes — cross-shop
  // rollups belong at the BRAND scope.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const timer = setTimeout(() => {
      const params: ListParams = {
        page: 1,
        page_size: 20,
        ordering: "-created_at",
        scope: currentItem.scope,
        ...(query.trim() ? { search: query.trim() } : {}),
      };
      if (currentItem.scope === "SHOP" && currentItem.shop_id !== null) {
        params.shop = currentItem.shop_id;
      }
      listActionItems(params)
        .then((resp) => {
          const filtered = resp.results.filter(
            (r) => r.id !== currentItem.id && r.source === "AI",
          );
          setResults(filtered);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [open, query, currentItem.id, currentItem.scope, currentItem.shop_id]);

  const selectedItem = useMemo(
    () => results.find((r) => r.id === selectedId) ?? null,
    [results, selectedId],
  );

  const handleConfirm = () => {
    if (selectedItem === null) return;
    onPicked(selectedItem.id, selectedItem);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="default"
      title="Mark as duplicate of"
      subtitle={currentItem.title}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center px-4 py-2 bg-white text-ink border border-line rounded-md text-[14px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={selectedId === null}
            className={`inline-flex items-center px-4 py-2 rounded-md text-[14px] font-semibold bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover ${
              selectedId === null ? "opacity-50 cursor-not-allowed pointer-events-none" : ""
            }`}
          >
            Select as primary
          </button>
        </>
      }
    >
      <div className="p-4 space-y-3">
        <div className="relative">
          <Search
            size={14}
            className="text-muted absolute left-3 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search action items…"
            aria-label="Search action items"
            aria-controls="dup-picker-results"
            className="w-full pl-9 px-4 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          />
        </div>
        <div
          id="dup-picker-results"
          role="listbox"
          className="mt-2 max-h-[280px] overflow-y-auto border border-line rounded-md"
        >
          {loading ? (
            <div className="text-[14px] text-muted px-4 py-4 text-center">Loading…</div>
          ) : results.length === 0 ? (
            <div className="text-[14px] text-muted px-4 py-4 text-center">
              No matching items found.
            </div>
          ) : (
            results.map((item) => {
              const isSelected = item.id === selectedId;
              return (
                <div
                  key={item.id}
                  role="option"
                  aria-selected={isSelected}
                  tabIndex={0}
                  onClick={() => setSelectedId(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(item.id);
                    }
                  }}
                  className={`flex flex-col px-4 py-2 cursor-pointer border-b border-line-soft last:border-b-0 ${
                    isSelected ? "bg-yellow-tint" : "hover:bg-line-soft"
                  }`}
                >
                  <span className="text-[14px] font-semibold text-ink">{item.title}</span>
                  <span className="text-[12px] text-muted mt-1">
                    {item.scope === "SHOP" ? (item.shop_name ? `Shop · ${item.shop_name}` : "Shop") : "Brand"}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </Modal>
  );
}
