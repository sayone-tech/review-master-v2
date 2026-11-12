import type { ReactNode } from "react";
import { avgPerCall, formatCost, formatCount, formatTokens } from "./format";
import { Money } from "./Money";
import type { CostSummaryTotals } from "./types";

function Cell({
  label,
  value,
  footer,
  title,
  className = "",
}: {
  label: string;
  value: ReactNode;
  footer: string;
  title?: string;
  className?: string;
}) {
  return (
    <div className={`bg-white px-4 py-3.5 ${className}`}>
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="mt-1 text-[22px] font-semibold leading-tight tracking-[-0.01em] text-ink tabular-nums" title={title}>
        {value}
      </dd>
      <dd className="mt-1 text-[12px] text-muted">{footer}</dd>
    </div>
  );
}

/** One card, four hairline-divided cells (2×2 below lg; cost and calls full-width on phones). */
export function SummaryStrip({
  totals,
  costFooter,
}: {
  totals: CostSummaryTotals;
  costFooter?: string;
}) {
  const avg = (tokens: number) => formatCount(Math.round(avgPerCall(tokens, totals.success_calls)));
  const orgs = `${formatCount(totals.org_count)} ${totals.org_count === 1 ? "organisation" : "organisations"}`;
  return (
    <dl
      className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line bg-line lg:grid-cols-4"
      data-testid="cost-summary"
    >
      <Cell
        className="col-span-2 sm:col-span-1"
        label="Total cost"
        value={<Money value={formatCost(totals.cost)} />}
        footer={costFooter ?? `Across ${orgs}`}
      />
      <Cell
        className="col-span-2 sm:col-span-1"
        label="API calls"
        value={formatCount(totals.calls)}
        footer={`${formatCount(totals.success_calls)} succeeded, ${formatCount(totals.failed_calls)} failed, ${formatCount(totals.moderated_calls)} moderated`}
      />
      <Cell
        label="Input tokens"
        value={formatTokens(totals.input_tokens)}
        title={formatCount(totals.input_tokens)}
        footer={`Avg ${avg(totals.input_tokens)} per call`}
      />
      <Cell
        label="Output tokens"
        value={formatTokens(totals.output_tokens)}
        title={formatCount(totals.output_tokens)}
        footer={`Avg ${avg(totals.output_tokens)} per call`}
      />
    </dl>
  );
}
