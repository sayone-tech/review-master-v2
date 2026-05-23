// Phase 21-04 — TypePill component per UI-SPEC §7.
// Renders a coloured pill for entity_type: review (blue) / action_item (amber).

import type { AuditLogRow } from "./types";

interface PillStyle {
  label: string;
  bg: string;
  text: string;
}

const TYPE_PILL: Record<AuditLogRow["entity_type"], PillStyle> = {
  review: { label: "Reply", bg: "bg-blue-tint", text: "text-blue" },
  action_item: { label: "Action Item", bg: "bg-amber-tint", text: "text-amber" },
};

interface Props {
  entityType: string;
}

export function TypePill({ entityType }: Props) {
  const pill = (TYPE_PILL as Record<string, PillStyle | undefined>)[entityType];
  if (!pill) {
    return <span className="text-muted text-[12px]">{entityType}</span>;
  }
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap text-[12px] font-semibold rounded-full px-2 py-1 ${pill.bg} ${pill.text}`}
    >
      {pill.label}
    </span>
  );
}
