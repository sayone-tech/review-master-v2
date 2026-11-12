import { formatCost, requestTypeLabel } from "./format";
import { Money } from "./Money";
import type { RequestTypeCosts } from "./types";

export function RequestTypeBadges({ costs }: { costs: RequestTypeCosts }) {
  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(costs).map(([type, cost]) => (
        <span
          key={type}
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-line-soft px-2 py-0.5 text-[12px] text-ink"
        >
          <span>{requestTypeLabel(type)}</span>
          <Money value={formatCost(cost)} className="text-muted" />
        </span>
      ))}
    </div>
  );
}
