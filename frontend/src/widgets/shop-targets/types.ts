export interface TargetRow {
  id: number;
  period_type: "WEEK" | "MONTH";
  target_count: number;
  received_count: number;
  pct: number;
  period_label: string;
  days_remaining: number;
}

export interface SetTargetPayload {
  period_type: "WEEK" | "MONTH";
  target_count: number;
}
