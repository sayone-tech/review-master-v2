import { CheckCircle, Crown, Users } from "lucide-react";
import type { TeamStats } from "./types";

export function TeamStatsCards({ stats }: { stats: TeamStats }) {
  return (
    <div className="flex gap-4">
      <div className="flex-1 bg-white border border-line rounded-card p-4 flex items-center gap-3">
        <Users size={20} className="text-muted shrink-0" aria-hidden="true" />
        <div>
          <div className="text-[24px] font-semibold text-ink">{stats.total_members}</div>
          <div className="text-[12px] font-normal text-muted">Total Members</div>
        </div>
      </div>
      <div className="flex-1 bg-white border border-line rounded-card p-4 flex items-center gap-3">
        <Crown size={20} className="text-muted shrink-0" aria-hidden="true" />
        <div>
          <div className="text-[24px] font-semibold text-ink">{stats.managers}</div>
          <div className="text-[12px] font-normal text-muted">Managers</div>
        </div>
      </div>
      <div className="flex-1 bg-white border border-line rounded-card p-4 flex items-center gap-3">
        <CheckCircle size={20} className="text-muted shrink-0" aria-hidden="true" />
        <div>
          <div className="text-[24px] font-semibold text-ink">{stats.active_members}</div>
          <div className="text-[12px] font-normal text-muted">Active Members</div>
        </div>
      </div>
    </div>
  );
}
