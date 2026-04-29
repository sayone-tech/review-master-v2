export type ConnectionMethod = "GOOGLE_OAUTH" | "NOT_CONNECTED";
export type ConnectionStatus =
  | "CONNECTED"
  | "EXPIRED"
  | "ERROR"
  | "QUOTA_EXCEEDED"
  | "NOT_CONNECTED";

export interface ShopRow {
  id: number;
  name: string;
  phone: string;
  street_address: string;
  place_id: string;
  connection_method: ConnectionMethod;
  connection_status: ConnectionStatus;
  is_active: boolean;
  region: number | null;
  region_name: string;
  region_region_id: string;
  created_at: string;
  updated_at: string;
}

export interface AllocationStatus {
  current: number;
  max: number;
  at_limit: boolean;
}

export interface ShopsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ShopRow[];
  allocation_status: AllocationStatus;
  has_regions: boolean;
}

export interface ShopCreatePayload {
  name: string;
  region: number;
  connection_method: ConnectionMethod;
  place_id?: string;
  google_refresh_token?: string;
  phone?: string;
  street_address?: string;
}

export interface ShopUpdatePayload {
  name?: string;
  phone?: string;
  region?: number;
  street_address?: string;
}

export interface ShopFilterParams {
  search?: string;
  status?: "active" | "inactive" | "";
  region?: number | "";
  page?: number;
  page_size?: number;
}
