import { Info } from "lucide-react";
import { formatCost, formatCount, formatTokens } from "./format";
import { Money, ShareBar } from "./Money";
import { NeutralBadge } from "./PageHeader";
import { RequestTypeBadges } from "./RequestTypeBadges";
import { SortHeader, TD, TD_NUM, TH } from "./SortHeader";
import type { ShopCostRow, ShopSortKey, UnattributedCost } from "./types";

const COLUMNS: { key: ShopSortKey; label: string; right: boolean }[] = [
  { key: "name", label: "Shop", right: false },
  { key: "calls", label: "API calls", right: true },
  { key: "input_tokens", label: "Input tokens", right: true },
  { key: "output_tokens", label: "Output tokens", right: true },
  { key: "cost", label: "Cost", right: true },
];

export const UNATTRIBUTED_HINT = "Calls whose review was deleted, so they are not linked to any shop";

interface Props {
  rows: ShopCostRow[];
  unattributed: UnattributedCost | null;
  sort: string;
  onSort: (sort: string) => void;
  /** Period total cost; draws each row's share bar when given. */
  totalCost?: number;
}

export function ShopTable({ rows, unattributed, sort, onSort, totalCost = 0 }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-[13.5px]">
        <thead>
          <tr className="border-y border-line bg-[#FBFBFB]">
            {COLUMNS.map((c) => (
              <SortHeader key={c.key} label={c.label} column={c.key} sort={sort} onSort={onSort} right={c.right} />
            ))}
            <th scope="col" className={`${TH} text-left`}>
              By request type
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.shop_id} className="border-b border-line-soft last:border-0">
              <td className={TD}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink">{r.name}</span>
                  {r.region_name && <NeutralBadge>{r.region_name}</NeutralBadge>}
                </div>
              </td>
              <td className={TD_NUM}>{formatCount(r.calls)}</td>
              <td className={TD_NUM} title={formatCount(r.input_tokens)}>
                {formatTokens(r.input_tokens)}
              </td>
              <td className={TD_NUM} title={formatCount(r.output_tokens)}>
                {formatTokens(r.output_tokens)}
              </td>
              <td className={TD_NUM}>
                <Money value={formatCost(r.cost)} className="font-medium text-ink" />
                <ShareBar cost={r.cost} total={totalCost} />
              </td>
              <td className={TD}>
                <RequestTypeBadges costs={r.by_request_type} />
              </td>
            </tr>
          ))}
          {unattributed && (
            <tr data-testid="unattributed-row" className="text-muted">
              <td className={TD}>
                <span className="inline-flex items-center gap-1.5">
                  Unattributed
                  <span title={UNATTRIBUTED_HINT} className="inline-flex text-faint">
                    <Info size={13} aria-hidden="true" />
                    <span className="sr-only">{UNATTRIBUTED_HINT}</span>
                  </span>
                </span>
              </td>
              <td className={TD_NUM}>{formatCount(unattributed.calls)}</td>
              <td className={TD_NUM} title={formatCount(unattributed.input_tokens)}>
                {formatTokens(unattributed.input_tokens)}
              </td>
              <td className={TD_NUM} title={formatCount(unattributed.output_tokens)}>
                {formatTokens(unattributed.output_tokens)}
              </td>
              <td className={TD_NUM}>
                <Money value={formatCost(unattributed.cost)} />
                <ShareBar cost={unattributed.cost} total={totalCost} />
              </td>
              <td className={TD}>
                <RequestTypeBadges costs={unattributed.by_request_type} />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
