import { CircleDollarSign, Building2, Phone, Coins } from "lucide-react";
import type { ReactNode } from "react";
import { avgPerCall, formatCost, formatCount, formatTokens } from "./format";
import type { CostSummaryTotals } from "./types";

function Card({
  icon,
  label,
  value,
  footer,
  title,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  footer: string;
  title?: string;
}) {
  return (
    <div className="bg-white border border-line rounded-card p-4">
      <div className="flex items-center gap-2 text-[12px] text-muted">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-[24px] font-semibold text-ink" title={title}>
        {value}
      </div>
      <div className="mt-1 text-[12px] text-muted">{footer}</div>
    </div>
  );
}

export function KpiRow({
  totals,
  orgLabel = "organisations",
}: {
  totals: CostSummaryTotals;
  orgLabel?: string;
}) {
  const tokens = totals.input_tokens + totals.output_tokens;
  const avg = Math.round(avgPerCall(tokens, totals.success_calls));
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card
        icon={<CircleDollarSign size={14} />}
        label="Total cost"
        value={formatCost(totals.cost)}
        footer={`Across ${formatCount(totals.org_count)} ${orgLabel}`}
      />
      <Card
        icon={<Phone size={14} />}
        label="AI calls"
        value={formatCount(totals.calls)}
        footer={`${formatCount(totals.success_calls)} succeeded · ${formatCount(totals.failed_calls)} failed · ${formatCount(totals.moderated_calls)} moderated`}
      />
      <Card
        icon={<Coins size={14} />}
        label="Tokens"
        value={formatTokens(tokens)}
        title={formatCount(tokens)}
        footer={`Avg ${formatCount(avg)} per call`}
      />
      <Card
        icon={<Building2 size={14} />}
        label="Active shops"
        value={formatCount(totals.active_shops)}
        footer="With AI usage in this period"
      />
    </div>
  );
}
