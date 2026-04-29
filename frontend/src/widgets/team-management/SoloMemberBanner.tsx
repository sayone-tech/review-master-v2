export function SoloMemberBanner() {
  return (
    <div className="bg-yellow-tint border border-yellow/40 rounded-md px-4 py-3 text-[14px] text-ink">
      You&apos;re the only member. Invite your team to get started.{" "}
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("team:open-add"))}
        className="text-yellow-hover underline font-semibold"
      >
        Add Team Member
      </button>
    </div>
  );
}
