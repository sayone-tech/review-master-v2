// Phase 13 Plan 07 — Priority dot + label per UI-SPEC §Color (Priority indicator colour map).
import type { ActionItemPriority } from "./types";

const COLOR_MAP: Record<ActionItemPriority, { dot: string; text: string; label: string }> = {
  HIGH: { dot: "#DC2626", text: "text-red", label: "High" },
  MEDIUM: { dot: "#D97706", text: "text-amber", label: "Medium" },
  LOW: { dot: "#52525B", text: "text-muted", label: "Low" },
};

interface Props {
  priority: ActionItemPriority;
}

export function PriorityIndicator({ priority }: Props) {
  const cfg = COLOR_MAP[priority];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[14px] ${cfg.text}`}>
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ backgroundColor: cfg.dot }}
        aria-hidden="true"
      />
      {cfg.label}
    </span>
  );
}
