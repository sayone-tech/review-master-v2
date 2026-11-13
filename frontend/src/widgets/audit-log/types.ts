// Phase 21-04 — Audit log types and frontend label maps.
// Mirrors AuditLogReadSerializer (apps/common/serializers.py).

export interface AuditLogRow {
  id: string;
  created_at: string;
  entity_type: "review" | "action_item" | "shop" | "organisation";
  entity_id: string;
  action: string;
  actor_id: number | null;
  actor_name: string | null;
  // CVIS-05: shop's name for shop credit rows; null for every other row.
  shop_name: string | null;
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
  /** A user id, or "platform" for the single generic "Review Bear Admin" option (CVIS-07). */
  id: number | "platform";
  full_name: string;
}

// D-20: Frontend action -> human-readable label.
// Unknown actions render their raw `action` string in text-muted.
export const ACTION_LABEL: Record<string, string> = {
  reply_posted: "Reply posted",
  reply_deleted: "Reply deleted",
  reply_failed: "Reply failed",
  // CVIS-06: review-level event; carries the tone, never credit numbers.
  ai_reply_generated: "AI reply generated",
  "action_item.created": "Action item created",
  "action_item.status_changed": "Status changed",
  "action_item.assigned": "Assigned",
  "action_item.note_added": "Note added",
  "action_item.merged": "Merged as duplicate",
  // CVIS-05: credit events (Org Admin only).
  "shop.credits.allocated": "Credits allocated",
  "shop.credits.bonus_allocated": "Bonus credits added",
  "shop.credits.consumed": "Credits used",
  "shop.credits.late_commit": "Credits used (late)",
  "shop.credits.refunded": "Credits refunded",
  "shop.credits.lapsed": "Credits lapsed",
  "organisation.credits.set": "Monthly credits updated",
};
