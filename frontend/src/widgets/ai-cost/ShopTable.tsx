import { ArrowDown, ArrowUp } from "lucide-react";
import { formatCost, formatCount, formatTokens } from "./format";
import { RequestTypeBadges } from "./RequestTypeBadges";
import type { ShopCostRow, ShopSortKey, UnattributedCost } from "./types";

const COLUMNS: { key: ShopSortKey; label: string; right: boolean }[] = [
  { key: "name", label: "Shop", right: false },
  { key: "calls", label: "API Calls", right: true },
  { key: "input_tokens", label: "Input Tokens", right: true },
  { key: "output_tokens", label: "Output Tokens", right: true },
  { key: "cost", label: "Cost (USD)", right: true },
];

export const UNATTRIBUTED_HINT = "Calls whose review was deleted — not linked to any shop";

interface Props {
  rows: ShopCostRow[];
  unattributed: UnattributedCost | null;
  sort: string;
  onSort: (sort: string) => void;
}

export function ShopTable({ rows, unattributed, sort, onSort }: Props) {
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
                  {isActive && (desc ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                </button>
              </th>
            );
          })}
          <th scope="col" className="px-4 py-2 text-left font-medium">
            By Request Type
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.shop_id} className="border-b border-line last:border-0">
            <td className="px-4 py-3">
              <span className="font-medium text-ink">{r.name}</span>
              {r.region_name && (
                <span className="ml-2 rounded-sm bg-line-soft px-2 py-0.5 text-[11px] text-muted">
                  {r.region_name}
                </span>
              )}
            </td>
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
        {unattributed && (
          <tr data-testid="unattributed-row" className="text-muted" title={UNATTRIBUTED_HINT}>
            <td className="px-4 py-3 italic">Unattributed</td>
            <td className="px-4 py-3 text-right">{formatCount(unattributed.calls)}</td>
            <td className="px-4 py-3 text-right" title={formatCount(unattributed.input_tokens)}>
              {formatTokens(unattributed.input_tokens)}
            </td>
            <td className="px-4 py-3 text-right" title={formatCount(unattributed.output_tokens)}>
              {formatTokens(unattributed.output_tokens)}
            </td>
            <td className="px-4 py-3 text-right font-medium">{formatCost(unattributed.cost)}</td>
            <td className="px-4 py-3">
              <RequestTypeBadges costs={unattributed.by_request_type} />
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
