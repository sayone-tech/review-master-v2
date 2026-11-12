import { formatCost, requestTypeLabel } from "./format";
import type { RequestTypeCosts } from "./types";

export function RequestTypeBadges({ costs }: { costs: RequestTypeCosts }) {
  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(costs).map(([type, cost]) => (
        <span
          key={type}
          className="inline-flex items-center gap-1 rounded-sm bg-line-soft px-2 py-0.5 text-[11px] text-ink"
        >
          <span>{requestTypeLabel(type)}</span>
          <span className="text-muted">{formatCost(cost)}</span>
        </span>
      ))}
    </div>
  );
}
