import { Crown } from "lucide-react";
import type { AccessScopeRow, TeamMemberRow } from "./types";

const VISIBLE_LIMIT = 2;

export function AccessChips({ member }: { member: TeamMemberRow }) {
  if (member.role === "ORG_ADMIN") {
    return (
      <span
        style={{ backgroundColor: "#FEF3C7", color: "#D97706" }}
        className="inline-flex items-center gap-1 px-2 py-[2px] rounded-full text-[12px] font-semibold"
      >
        <Crown size={14} aria-hidden="true" />
        All stores
      </span>
    );
  }
  const scopes = member.access_scopes ?? [];
  if (scopes.length === 0) {
    return <span className="text-muted text-[12px]">—</span>;
  }
  const visible = scopes.slice(0, VISIBLE_LIMIT);
  const overflow = scopes.length - VISIBLE_LIMIT;
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {visible.map((s) => renderScope(s))}
      {overflow > 0 && (
        <span className="inline-flex items-center px-2 py-[4px] rounded-full text-[12px] font-normal italic bg-line-soft text-muted">
          +{overflow} more
        </span>
      )}
    </div>
  );
}

function renderScope(s: AccessScopeRow) {
  if (s.scope_type === "REGION") {
    return (
      <span
        key={s.id}
        className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-medium bg-line-soft text-ink font-mono"
      >
        {s.region_region_id ?? s.region_name ?? "—"}
      </span>
    );
  }
  return (
    <span
      key={s.id}
      className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-medium bg-blue-tint text-blue"
    >
      {s.shop_name ?? "—"}
    </span>
  );
}
