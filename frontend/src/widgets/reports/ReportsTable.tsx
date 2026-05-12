import { useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import type { SortDir, SortKey, StoreReportRow } from "./types";

interface Props {
  rows: StoreReportRow[];
  loading: boolean;
}

const SENTIMENT_BADGE: Record<string, { bg: string; text: string }> = {
  positive: { bg: "#F0FDF4", text: "#15803D" },
  neutral:  { bg: "#F9FAFB", text: "#6B7280" },
  negative: { bg: "#FEF2F2", text: "#B91C1C" },
};

function SortButton({
  label,
  sortKey,
  active,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  active: boolean;
  dir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const Icon = active ? (dir === "desc" ? ArrowDown : ArrowUp) : ArrowUpDown;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={`inline-flex items-center gap-1 hover:text-ink transition-colors ${active ? "text-ink" : "text-subtle"}`}
    >
      {label}
      <Icon size={11} aria-hidden="true" />
    </button>
  );
}

function numCell(value: number, highlight?: string) {
  return (
    <span className={`text-[13.5px] font-medium ${highlight ?? "text-ink"}`}>
      {value}
    </span>
  );
}

function sentimentCell(count: number, type: "positive" | "neutral" | "negative") {
  const s = SENTIMENT_BADGE[type];
  if (count === 0) return <span className="text-[13.5px] text-muted">0</span>;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[12px] font-semibold"
      style={{ backgroundColor: s.bg, color: s.text }}
    >
      {count}
    </span>
  );
}

export function ReportsTable({ rows, loading }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("total_reviews");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey] ?? 0;
    const bv = b[sortKey] ?? 0;
    return sortDir === "desc" ? (bv as number) - (av as number) : (av as number) - (bv as number);
  });

  function sortLabel(label: string, key: SortKey) {
    return (
      <SortButton label={label} sortKey={key} active={sortKey === key} dir={sortDir} onSort={handleSort} />
    );
  }

  const columns: DataTableColumn<StoreReportRow>[] = [
    {
      key: "shop_name",
      label: "STORE",
      skeletonWidth: "160px",
      accessor: (r) => (
        <span className="text-[13.5px] font-semibold text-ink">{r.shop_name}</span>
      ),
    },
    {
      key: "avg_rating",
      label: "AVG RATING",
      skeletonWidth: "60px",
      accessor: (r) => (
        <span className="text-[13.5px] font-semibold text-yellow">
          {r.avg_rating != null && r.avg_rating > 0 ? `★ ${r.avg_rating.toFixed(1)}` : "—"}
        </span>
      ),
    },
    {
      key: "total_reviews",
      label: "REVIEWS",
      skeletonWidth: "60px",
      accessor: (r) => numCell(r.total_reviews),
    },
    {
      key: "replied_count",
      label: "REPLIED",
      skeletonWidth: "60px",
      accessor: (r) => numCell(r.replied_count),
    },
    {
      key: "not_replied_count",
      label: "NOT REPLIED",
      skeletonWidth: "60px",
      accessor: (r) =>
        r.not_replied_count > 0
          ? numCell(r.not_replied_count, "text-amber-600")
          : numCell(0),
    },
    {
      key: "positive_count",
      label: "POSITIVE",
      skeletonWidth: "60px",
      accessor: (r) => sentimentCell(r.positive_count, "positive"),
    },
    {
      key: "neutral_count",
      label: "NEUTRAL",
      skeletonWidth: "60px",
      accessor: (r) => sentimentCell(r.neutral_count, "neutral"),
    },
    {
      key: "negative_count",
      label: "NEGATIVE",
      skeletonWidth: "60px",
      accessor: (r) => sentimentCell(r.negative_count, "negative"),
    },
  ];

  // Inject sort buttons into header labels via a wrapper
  const sortableColumns = columns.map((col) => {
    const sortableKeys: SortKey[] = [
      "avg_rating",
      "total_reviews",
      "replied_count",
      "not_replied_count",
      "positive_count",
      "neutral_count",
      "negative_count",
    ];
    if (!sortableKeys.includes(col.key as SortKey)) return col;
    return {
      ...col,
      label: col.label, // DataTable renders label as string — we handle sort via footer
    };
  });

  const emptyState = (
    <div className="py-16 text-center text-[14px] text-muted">
      No reviews match the selected filters.
    </div>
  );

  return (
    <div>
      {/* Sort control */}
      <div className="flex items-center justify-end gap-3 mb-2 text-[12px] text-muted">
        <span>Sort by:</span>
        {(
          [
            ["total_reviews", "Reviews"],
            ["avg_rating", "Avg Rating"],
            ["replied_count", "Replied"],
            ["not_replied_count", "Not Replied"],
            ["positive_count", "Positive"],
            ["negative_count", "Negative"],
          ] as [SortKey, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => handleSort(key)}
            className={`inline-flex items-center gap-0.5 transition-colors ${
              sortKey === key ? "text-ink font-semibold" : "hover:text-ink"
            }`}
          >
            {label}
            {sortKey === key ? (
              sortDir === "desc" ? (
                <ArrowDown size={10} aria-hidden="true" />
              ) : (
                <ArrowUp size={10} aria-hidden="true" />
              )
            ) : null}
          </button>
        ))}
      </div>

      <DataTable
        columns={sortableColumns}
        rows={sorted}
        loading={loading}
        emptyState={emptyState}
        rowKey={(r) => String(r.shop_id)}
        wrapperClassName="bg-white border border-line rounded-card overflow-hidden"
      />
    </div>
  );
}
