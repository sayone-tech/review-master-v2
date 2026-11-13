// Single source of truth for organisation types (mirrors Organisation.OrgType).
export const ORG_TYPE_OPTIONS = [
  { value: "RETAIL", label: "Retail" },
  { value: "RESTAURANT", label: "Restaurant & Cafe" },
  { value: "PHARMACY", label: "Pharmacy" },
  { value: "SUPERMARKET", label: "Supermarket" },
  { value: "CLINIC", label: "Clinic" },
  { value: "HOSPITAL", label: "Hospital" },
  { value: "SALON", label: "Salon" },
  { value: "SPA", label: "Spa" },
  { value: "HOTEL_RESORT", label: "Hotel & Resort" },
  { value: "GYM_FITNESS", label: "Gym & Fitness" },
] as const;

export type OrgType = (typeof ORG_TYPE_OPTIONS)[number]["value"];
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
  allow_custom_sync_depth: boolean;
  monthly_credit_allocation: number;
  current_month_credit_allocation: number;
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
  allow_custom_sync_depth: boolean;
  monthly_credit_allocation: number;
}

export type UpdateOrgPayload = Partial<{
  name: string;
  org_type: OrgType;
  address: string;
  number_of_stores: number;
  status: "ACTIVE" | "DISABLED";
  allow_custom_sync_depth: boolean;
  monthly_credit_allocation: number;
}>;

export type ApiFieldErrors = Record<string, string[]>;

export const ORG_TYPE_LABELS = Object.fromEntries(
  ORG_TYPE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<OrgType, string>;

export const ORG_STATUS_LABELS: Record<Exclude<OrgStatus, "DELETED">, string> = {
  ACTIVE: "Active",
  DISABLED: "Disabled",
};
