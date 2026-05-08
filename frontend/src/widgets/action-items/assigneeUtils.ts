import type { ActionItemScope, TeamMember } from "./types";

/**
 * Returns the members eligible to be assigned to an action item.
 *
 * BRAND scope → org admins only (staff can't see brand items).
 * SHOP scope  → org admins + staff members who have access to that specific shop.
 */
export function getAssignableMembers(
  teamMembers: TeamMember[],
  scope: ActionItemScope,
  shopId: number | null | undefined,
): TeamMember[] {
  if (scope === "BRAND") {
    return teamMembers.filter((m) => m.role === "ORG_ADMIN");
  }
  return teamMembers.filter(
    (m) => m.role === "ORG_ADMIN" || m.shop_ids.includes(shopId ?? -1),
  );
}
