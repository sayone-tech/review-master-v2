// Phase 21-04 — Audit log types and frontend label maps.
// Mirrors AuditLogReadSerializer (apps/common/serializers.py).

export interface AuditLogRow {
  id: string;
  created_at: string;
  entity_type: "review" | "action_item";
  entity_id: string;
  action: string;
  actor_id: number | null;
  actor_name: string | null;
  after_data: Record<string, unknown> | null;
}

export interface AuditLogResponse {
  next: string | null;
  previous: string | null;
  results: AuditLogRow[];
}

export interface FilterParams {
  entity_type?: string;
  actor?: string;
  date_from?: string;
  date_to?: string;
}

export interface ActorOption {
  id: number;
  full_name: string;
}

// D-20: Frontend action -> human-readable label.
// Unknown actions render their raw `action` string in text-muted.
export const ACTION_LABEL: Record<string, string> = {
  reply_posted: "Reply posted",
  reply_deleted: "Reply deleted",
  reply_failed: "Reply failed",
  "action_item.created": "Action item created",
  "action_item.status_changed": "Status changed",
  "action_item.assigned": "Assigned",
  "action_item.note_added": "Note added",
  "action_item.merged": "Merged as duplicate",
};
