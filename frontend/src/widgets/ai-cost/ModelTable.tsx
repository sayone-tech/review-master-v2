import { formatCost, formatCount, formatTokens } from "./format";
import { Money } from "./Money";
import { TD, TD_NUM, TH } from "./SortHeader";
import type { ModelCostRow } from "./types";

/** Narrow side table: tokens shown as a visible secondary line under the calls value. */
export function ModelTable({ rows }: { rows: ModelCostRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="border-y border-line bg-[#FBFBFB]">
            <th scope="col" className={`${TH} text-left`}>Model</th>
            <th scope="col" className={`${TH} text-right`}>API calls</th>
            <th scope="col" className={`${TH} text-right`}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model} className="border-b border-line-soft last:border-0">
              <td className={`${TD} break-all font-medium text-ink`}>{r.model}</td>
              <td className={TD_NUM}>
                {formatCount(r.calls)}
                <span className="block whitespace-nowrap text-[12px] font-normal text-muted">
                  {formatTokens(r.input_tokens)} in · {formatTokens(r.output_tokens)} out
                </span>
              </td>
              <td className={TD_NUM}>
                <Money value={formatCost(r.cost)} className="font-medium text-ink" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
