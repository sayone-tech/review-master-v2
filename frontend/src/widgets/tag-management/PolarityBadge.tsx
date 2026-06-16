// Phase 25-03 — Polarity badge for OrgCanonicalTag polarity_type values.
// Color alone does not distinguish polarity — each badge also carries the text label.

import type { PolarityType } from "./types";

const BADGE: Record<PolarityType, { label: string; cls: string }> = {
  always_positive: { label: "Always Positive", cls: "bg-green-tint text-[#166534]" },
  always_negative: { label: "Always Negative", cls: "bg-red-tint text-[#991B1B]" },
  mixed: { label: "Mixed", cls: "bg-amber-tint text-[#92400E]" },
};

interface Props {
  polarity: PolarityType;
}

export function PolarityBadge({ polarity }: Props) {
  const { label, cls } = BADGE[polarity] ?? BADGE.mixed;
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-sm text-[12px] font-medium ${cls}`}
    >
      {label}
    </span>
  );
}
