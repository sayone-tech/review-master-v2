export type NotificationType =
  | "new_review"
  | "new_action_item"
  | "action_item_assigned";

export interface NotificationRow {
  id: number;
  notification_type: NotificationType;
  title: string;
  target_url: string;
  is_read: boolean;
  shop_id: number | null;
  shop_name: string | null;
  action_item_id: number | null;
  review_id: number | null;
  created_at: string;
}

export interface BellResponse {
  unread_count: number;
  items: NotificationRow[];
}
