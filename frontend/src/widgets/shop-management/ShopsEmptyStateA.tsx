import { Map } from "lucide-react";

export function ShopsEmptyStateA() {
  return (
    <div
      data-testid="empty-state-a"
      className="bg-white border border-line rounded-card p-12 flex flex-col items-center text-center"
    >
      <Map size={32} className="text-muted mb-3" aria-hidden="true" />
      <h3 className="text-[16px] font-semibold text-ink mb-1">Create a region first</h3>
      <p className="text-[13.5px] text-muted mb-4">
        Shops belong to a region. Add a region to start tracking shops.
      </p>
      <a
        href="/admin/org/regions/"
        className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        Go to Regions
      </a>
    </div>
  );
}
