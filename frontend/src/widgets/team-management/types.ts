export interface AccessScopeRow {
  id: number;
  scope_type: "REGION" | "SHOP";
  region: number | null;
  region_name: string | null;
  region_region_id: string | null;
  shop: number | null;
  shop_name: string | null;
}

export interface TeamMemberRow {
  id: number;
  full_name: string;
  email: string;
  role: "ORG_ADMIN" | "STAFF_ADMIN";
  is_active: boolean;
  invited_at: string | null;
  accepted_at: string | null;
  status: "PENDING" | "ACTIVE" | "DISABLED";
  access_scopes: AccessScopeRow[];
}

export interface TeamFilterParams {
  search?: string;
  region_id?: number;
  shop_id?: number;
  page?: number;
  page_size?: number;
}

export interface TeamListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: TeamMemberRow[];
}

export interface TeamStats {
  total_members: number;
  managers: number;
  active_members: number;
}

export interface TeamCreatePayload {
  full_name: string;
  email: string;
  invited_for_role: "ORG_ADMIN" | "STAFF_ADMIN";
  region_ids?: number[];
  shop_ids?: number[];
}

export interface TeamUpdatePayload {
  full_name?: string;
  role?: "ORG_ADMIN" | "STAFF_ADMIN";
  region_ids?: number[];
  shop_ids?: number[];
}

export interface RegionOption {
  id: number;
  region_id: string;
  name: string;
}

export interface ShopOption {
  id: number;
  name: string;
  region: number;
  region_id: string;
  region_name: string;
}
