export type OrgType = "RETAIL" | "RESTAURANT" | "PHARMACY" | "SUPERMARKET";
export type OrgStatus = "ACTIVE" | "DISABLED" | "DELETED";
export type ActivationStatus = "pending" | "active" | "expired";

export interface OrgRow {
  id: number;
  name: string;
  org_type: OrgType;
  email: string;
  address: string;
  number_of_stores: number;
  status: OrgStatus;
  created_at: string;
  total_stores: number;
  active_stores: number;
  activation_status: ActivationStatus;
  last_invited_at: string | null;
}

export interface ListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: OrgRow[];
}

export interface CreateOrgPayload {
  name: string;
  org_type: OrgType;
  email: string;
  address: string;
  number_of_stores: number;
}

export type UpdateOrgPayload = Partial<{
  name: string;
  org_type: OrgType;
  address: string;
  number_of_stores: number;
  status: "ACTIVE" | "DISABLED";
}>;

export type ApiFieldErrors = Record<string, string[]>;

export const ORG_TYPE_LABELS: Record<OrgType, string> = {
  RETAIL: "Retail",
  RESTAURANT: "Restaurant",
  PHARMACY: "Pharmacy",
  SUPERMARKET: "Supermarket",
};

export const ORG_STATUS_LABELS: Record<Exclude<OrgStatus, "DELETED">, string> = {
  ACTIVE: "Active",
  DISABLED: "Disabled",
};
