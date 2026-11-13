import { formatCost, formatCount, formatTokens, orgTypeLabel } from "./format";
import { Money, ShareBar } from "./Money";
import { NeutralBadge } from "./PageHeader";
import { RequestTypeBadges } from "./RequestTypeBadges";
import { SortHeader, TD, TD_NUM, TH } from "./SortHeader";
import type { OrgCostRow, OrgSortKey } from "./types";

const COLUMNS: { key: OrgSortKey; label: string; right: boolean }[] = [
  { key: "name", label: "Organisation", right: false },
  { key: "active_shops", label: "Active shops", right: true },
  { key: "calls", label: "API calls", right: true },
  { key: "input_tokens", label: "Input tokens", right: true },
  { key: "output_tokens", label: "Output tokens", right: true },
  { key: "cost", label: "Cost", right: true },
];

interface Props {
  rows: OrgCostRow[];
  sort: string;
  onSort: (sort: string) => void;
  onOpen: (orgId: number) => void;
  /** Query string (with leading "?") appended to org links, e.g. the active range. */
  query?: string;
  /** Period total cost; draws each row's share bar when given. */
  totalCost?: number;
}

export function OrgTable({ rows, sort, onSort, onOpen, query = "", totalCost = 0 }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-[13.5px]">
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
            <tr
              key={r.organisation_id}
              className="cursor-pointer border-b border-line-soft last:border-0 hover:bg-[#FBFBFB]"
              onClick={(e) => {
                if ((e.target as HTMLElement).closest("a")) return;
                onOpen(r.organisation_id);
              }}
            >
              <td className={TD}>
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={`/admin/ai-cost/organisations/${r.organisation_id}/${query}`}
                    className="rounded-sm font-semibold text-ink hover:underline underline-offset-2"
                    onClick={(e) => {
                      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                      e.preventDefault();
                      onOpen(r.organisation_id);
                    }}
                  >
                    {r.name}
                  </a>
                  <NeutralBadge>{orgTypeLabel(r.org_type)}</NeutralBadge>
                </div>
              </td>
              <td className={TD_NUM}>{formatCount(r.active_shops)}</td>
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
        </tbody>
      </table>
    </div>
  );
}
