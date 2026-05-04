// Phase 13 Plan 07 — REVW-08 final delivery: clickable AI action item chip.
//
// When `hasActionItems` is true (i.e., promoted ActionItem rows exist for this
// review per the backend `Review.has_action_items` annotation), the chip is
// rendered as a clickable anchor that navigates to the action items page
// pre-filtered by review. When false, the chip is non-interactive ("pending").
//
// Phase 12 originally rendered this as a non-interactive chip. Phase 13 replaces
// it per UI-SPEC §6.
import { Sparkles } from "lucide-react";

interface Props {
  count: number;
  reviewId: number;
  hasActionItems: boolean;
}

export function ActionItemChip({ count, reviewId, hasActionItems }: Props) {
  if (count <= 0) return null;
  const label = count === 1 ? "1 action item" : `${count} action items`;
  const baseClasses =
    "inline-flex items-center gap-1 px-2 py-0.5 text-[12px] font-semibold rounded-full bg-amber-tint text-amber";
  if (hasActionItems) {
    return (
      <a
        href={`/admin/org/action-items/?review=${reviewId}`}
        className={`${baseClasses} cursor-pointer hover:bg-[#FDE68A]`}
        title="View action items for this review"
        aria-label={label}
        data-testid="action-item-chip"
      >
        <Sparkles size={12} aria-hidden="true" />
        {label}
      </a>
    );
  }
  return (
    <span
      className={baseClasses}
      title="Action items pending"
      aria-label={label}
      data-testid="action-item-chip"
    >
      <Sparkles size={12} aria-hidden="true" />
      {label}
    </span>
  );
}
