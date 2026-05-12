import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { SortDir, SortKey, StoreReportRow } from "./types";

interface Props {
  rows: StoreReportRow[];
}

const TH_CLS = "px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-subtle cursor-pointer select-none whitespace-nowrap";
const TD_CLS = "px-4 py-3 text-[13.5px] text-ink";

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  const cls = `inline-block ml-1 ${active ? "text-ink" : "text-faint"}`;
  return active && dir === "asc"
    ? <ChevronUp size={12} className={cls} />
    : <ChevronDown size={12} className={cls} />;
}

export function ReportsTable({ rows }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("total_reviews");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(d => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    return sortDir === "desc" ? (bv as number) - (av as number) : (av as number) - (bv as number);
  });

  if (sorted.length === 0) {
    return (
      <div className="text-center py-16 text-muted text-[14px]">
        No reviews match the selected filters.
      </div>
    );
  }

  function th(label: string, key: SortKey) {
    return (
      <th className={TH_CLS} onClick={() => handleSort(key)}>
        {label}
        <SortIcon active={sortKey === key} dir={sortDir} />
      </th>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse">
        <thead className="bg-bg border-b border-line">
          <tr>
            <th className={TH_CLS + " cursor-default"}>Store</th>
            {th("★ Avg Rating", "avg_rating")}
            {th("Reviews", "total_reviews")}
            {th("Replied", "replied_count")}
            {th("Not Replied", "not_replied_count")}
            {th("😊 Positive", "positive_count")}
            {th("😐 Neutral", "neutral_count")}
            {th("😞 Negative", "negative_count")}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={row.shop_id}
              className={i % 2 === 0 ? "bg-white" : "bg-bg hover:bg-[#f9f9f9]"}
            >
              <td className={TD_CLS + " font-medium"}>{row.shop_name}</td>
              <td className={TD_CLS + " text-yellow font-semibold"}>
                {row.avg_rating > 0 ? row.avg_rating.toFixed(1) : "—"}
              </td>
              <td className={TD_CLS}>{row.total_reviews}</td>
              <td className={TD_CLS}>{row.replied_count}</td>
              <td className={TD_CLS + (row.not_replied_count > 0 ? " text-amber-600 font-medium" : "")}>
                {row.not_replied_count}
              </td>
              <td className={TD_CLS + " text-green-700"}>{row.positive_count}</td>
              <td className={TD_CLS + " text-muted"}>{row.neutral_count}</td>
              <td className={TD_CLS + (row.negative_count > 0 ? " text-red-600 font-medium" : "")}>
                {row.negative_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
