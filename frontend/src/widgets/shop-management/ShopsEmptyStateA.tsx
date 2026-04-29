import { Map } from "lucide-react";

export function ShopsEmptyStateA() {
  return (
    <div
      data-testid="empty-state-a"
      className="flex flex-col items-center justify-center py-16"
    >
      <Map size={40} className="text-faint" aria-hidden="true" />
      <h3 className="text-[15px] font-semibold text-ink mt-4">Create a region first</h3>
      <p className="text-[13.5px] text-muted mt-1.5">
        Shops belong to a region. Add a region to start tracking shops.
      </p>
      <a
        href="/admin/org/regions/"
        className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        Go to Regions
      </a>
    </div>
  );
}
