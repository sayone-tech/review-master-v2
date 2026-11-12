import { formatCost, formatCount, formatTokens } from "./format";
import type { ModelCostRow } from "./types";

export function ModelTable({ rows }: { rows: ModelCostRow[] }) {
  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-line bg-[#FBFBFB] text-[12px] text-muted">
          <th scope="col" className="px-4 py-2 text-left font-medium">Model</th>
          <th scope="col" className="px-4 py-2 text-right font-medium">API Calls</th>
          <th scope="col" className="px-4 py-2 text-right font-medium">Input Tokens</th>
          <th scope="col" className="px-4 py-2 text-right font-medium">Output Tokens</th>
          <th scope="col" className="px-4 py-2 text-right font-medium">Cost (USD)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.model} className="border-b border-line last:border-0">
            <td className="px-4 py-3 font-medium text-ink">{r.model}</td>
            <td className="px-4 py-3 text-right">{formatCount(r.calls)}</td>
            <td className="px-4 py-3 text-right" title={formatCount(r.input_tokens)}>
              {formatTokens(r.input_tokens)}
            </td>
            <td className="px-4 py-3 text-right" title={formatCount(r.output_tokens)}>
              {formatTokens(r.output_tokens)}
            </td>
            <td className="px-4 py-3 text-right font-medium text-ink">{formatCost(r.cost)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
