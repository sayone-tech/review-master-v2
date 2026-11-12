import { ArrowDown, ArrowUp } from "lucide-react";
import { formatCost, formatCount, formatTokens } from "./format";
import { RequestTypeBadges } from "./RequestTypeBadges";
import type { OrgCostRow, OrgSortKey } from "./types";

const COLUMNS: { key: OrgSortKey; label: string; right: boolean }[] = [
  { key: "name", label: "Organisation", right: false },
  { key: "active_shops", label: "Active shops", right: true },
  { key: "calls", label: "Calls", right: true },
  { key: "input_tokens", label: "Input tokens", right: true },
  { key: "output_tokens", label: "Output tokens", right: true },
  { key: "cost", label: "Cost", right: true },
];

interface Props {
  rows: OrgCostRow[];
  sort: string;
  onSort: (sort: string) => void;
  onOpen: (orgId: number) => void;
}

export function OrgTable({ rows, sort, onSort, onOpen }: Props) {
  const desc = sort.startsWith("-");
  const active = desc ? sort.slice(1) : sort;

  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-line bg-[#FBFBFB] text-[12px] text-muted">
          {COLUMNS.map((c) => {
            const isActive = active === c.key;
            return (
              <th
                key={c.key}
                scope="col"
                className={`px-4 py-2 font-medium ${c.right ? "text-right" : "text-left"}`}
                aria-sort={isActive ? (desc ? "descending" : "ascending") : "none"}
              >
                <button
                  type="button"
                  className="inline-flex items-center gap-1 hover:text-ink"
                  onClick={() => onSort(isActive && !desc ? `-${c.key}` : c.key)}
                >
                  {c.label}
                  {isActive &&
                    (desc ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                </button>
              </th>
            );
          })}
          <th scope="col" className="px-4 py-2 text-left font-medium">
            By type
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.organisation_id}
            className="cursor-pointer border-b border-line last:border-0 hover:bg-line-soft"
            onClick={() => onOpen(r.organisation_id)}
          >
            <td className="px-4 py-3 font-medium text-ink">{r.name}</td>
            <td className="px-4 py-3 text-right">{formatCount(r.active_shops)}</td>
            <td className="px-4 py-3 text-right">{formatCount(r.calls)}</td>
            <td className="px-4 py-3 text-right" title={formatCount(r.input_tokens)}>
              {formatTokens(r.input_tokens)}
            </td>
            <td className="px-4 py-3 text-right" title={formatCount(r.output_tokens)}>
              {formatTokens(r.output_tokens)}
            </td>
            <td className="px-4 py-3 text-right font-medium text-ink">{formatCost(r.cost)}</td>
            <td className="px-4 py-3">
              <RequestTypeBadges costs={r.by_request_type} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
