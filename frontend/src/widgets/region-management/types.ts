export interface RegionRow {
  id: number;
  name: string;
  region_id: string;
  created_at: string; // ISO 8601
}

export interface CreateRegionPayload {
  name: string;
  region_id: string;
}

export interface UpdateRegionPayload {
  name?: string;
  region_id?: string;
}

export interface RegionBlockedError {
  shop_count: number;
}
