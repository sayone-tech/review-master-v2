// STUB — replaced by Plan 05
import type { RegionOption, ShopOption } from "./types";

interface TeamModalsProps {
  regions: RegionOption[];
  activeShops: ShopOption[];
  currentUserId: number;
  managerCount: number;
}

export function TeamModals({ regions: _regions, activeShops: _activeShops, currentUserId: _currentUserId, managerCount: _managerCount }: TeamModalsProps) {
  return <div data-testid="team-modals-stub" />;
}
