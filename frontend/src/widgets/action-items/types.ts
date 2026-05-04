export type ActionItemStatus = "TODO" | "IN_PROGRESS" | "COMPLETE" | "WONT_DO";
export type ActionItemScope = "SHOP" | "BRAND";
export type ActionItemPriority = "HIGH" | "MEDIUM" | "LOW";
export type ActionItemSource = "AI" | "MANUAL";
export type UserRole = "ORG_ADMIN" | "STAFF_ADMIN" | "SUPERADMIN";

export interface ActionItemListRow {
  id: number;
  title: string;
  status: ActionItemStatus;
  scope: ActionItemScope;
  priority: ActionItemPriority;
  source: ActionItemSource;
  shop_id: number | null;
  shop_name: string | null;
  assignee_id: number | null;
  assignee_name: string | null;
  due_date: string | null;
  source_review_id: number | null;
  created_at: string;
}

export interface ActionItemNote {
  id: number;
  body: string;
  author_id: number | null;
  author_name: string | null;
  created_at: string;
}

export interface SourceReviewSnippet {
  id: number;
  comment: string;
  rating: number;
  reviewer_name: string;
}

export interface ActionItemDetail extends ActionItemListRow {
  notes: ActionItemNote[];
  source_review: SourceReviewSnippet | null;
  updated_at: string;
}

export interface PaginatedActionItems {
  count: number;
  next: string | null;
  previous: string | null;
  results: ActionItemListRow[];
}

export interface ListParams {
  page: number;
  page_size: number;
  ordering: string;
  shop?: number;
  status?: ActionItemStatus;
  scope?: ActionItemScope;
  assignee?: string;
  from_date?: string;
  to_date?: string;
  search?: string;
  review?: number;
}

export interface CreateActionItemPayload {
  title: string;
  scope: ActionItemScope;
  shop_id?: number | null;
  priority: ActionItemPriority;
  assignee_id?: number | null;
  due_date?: string | null;
  initial_note?: string | null;
}

export interface UpdatePayload {
  title: string;
  priority: ActionItemPriority;
  due_date: string | null;
  assignee_id: number | null;
}

export interface ShopOption {
  id: number;
  name: string;
}

export interface TeamMember {
  id: number;
  full_name: string;
}
