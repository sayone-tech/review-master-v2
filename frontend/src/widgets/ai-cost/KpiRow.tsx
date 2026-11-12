import { ArrowDownToLine, ArrowUpFromLine, CircleDollarSign, Phone } from "lucide-react";
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

export function KpiRow({ totals }: { totals: CostSummaryTotals }) {
  const avg = (tokens: number) => formatCount(Math.round(avgPerCall(tokens, totals.success_calls)));
  const orgs = `${formatCount(totals.org_count)} ${totals.org_count === 1 ? "organisation" : "organisations"}`;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card
        icon={<CircleDollarSign size={14} />}
        label="Total Cost"
        value={formatCost(totals.cost)}
        footer={`Across ${orgs}`}
      />
      <Card
        icon={<Phone size={14} />}
        label="Total API Calls"
        value={formatCount(totals.calls)}
        footer={`${formatCount(totals.success_calls)} succeeded · ${formatCount(totals.failed_calls)} failed · ${formatCount(totals.moderated_calls)} moderated`}
      />
      <Card
        icon={<ArrowDownToLine size={14} />}
        label="Total Input Tokens"
        value={formatTokens(totals.input_tokens)}
        title={formatCount(totals.input_tokens)}
        footer={`Avg ${avg(totals.input_tokens)} per call`}
      />
      <Card
        icon={<ArrowUpFromLine size={14} />}
        label="Total Output Tokens"
        value={formatTokens(totals.output_tokens)}
        title={formatCount(totals.output_tokens)}
        footer={`Avg ${avg(totals.output_tokens)} per call`}
      />
    </div>
  );
}
