import { Users } from "lucide-react";

export function TeamEmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center py-16"
      data-testid="team-empty-state"
    >
      <Users size={40} className="text-faint" />
      <h3 className="text-[15px] font-semibold text-ink mt-4">No team members yet.</h3>
      <p className="text-[13.5px] text-muted mt-1.5">
        Invite your first team member to get started.
      </p>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("team:open-add"))}
        className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        + Add Team Member
      </button>
    </div>
  );
}
