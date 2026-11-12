import { ArrowDown, ArrowUp } from "lucide-react";

export const TH = "px-4 py-2.5 text-[12px] font-medium text-muted whitespace-nowrap";
export const TD = "px-4 py-3";
export const TD_NUM = "px-4 py-3 text-right tabular-nums";

/** Sortable column header: ascending first, then toggles; exposes aria-sort. */
export function SortHeader({
  label,
  column,
  sort,
  onSort,
  right,
}: {
  label: string;
  column: string;
  sort: string;
  onSort: (sort: string) => void;
  right: boolean;
}) {
  const desc = sort.startsWith("-");
  const isActive = (desc ? sort.slice(1) : sort) === column;
  return (
    <th
      scope="col"
      className={`${TH} ${right ? "text-right" : "text-left"}`}
      aria-sort={isActive ? (desc ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        className={`inline-flex items-center gap-1 rounded-sm hover:text-ink ${isActive ? "text-ink" : ""}`}
        onClick={() => onSort(isActive && !desc ? `-${column}` : column)}
      >
        {label}
        {isActive && (desc ? <ArrowDown size={12} aria-hidden="true" /> : <ArrowUp size={12} aria-hidden="true" />)}
      </button>
    </th>
  );
}
