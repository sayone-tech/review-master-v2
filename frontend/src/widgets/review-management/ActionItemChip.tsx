// Phase 12 — Non-interactive AI action item count chip per UI-SPEC.md §3.
//
// Renders a small amber-tint chip on each review card showing the count of
// extracted_action_items returned by the GPT enrichment pipeline. Phase 12
// chip is intentionally non-interactive — clicking opens nothing. Phase 13
// will replace this with a clickable chip that opens the Action Item modal
// (REVW-08 full delivery).
//
// Tokens (from frontend/tailwind.config.js):
//   bg-amber-tint -> #FEF3C7
//   text-amber    -> #D97706
//
// These are the same tokens used by the "Analyzing…" pill in SentimentBadge,
// visually distinct from sentiment chips and signals AI-extracted content.
import { Sparkles } from "lucide-react";

interface Props {
  count: number;
}

export function ActionItemChip({ count }: Props) {
  if (count <= 0) return null;
  const label = count === 1 ? "1 action item" : `${count} action items`;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-[12px] font-semibold rounded-full bg-amber-tint text-amber"
      aria-label={label}
      data-testid="action-item-chip"
    >
      <Sparkles size={12} aria-hidden="true" />
      {label}
    </span>
  );
}
