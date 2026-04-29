import { Store } from "lucide-react";

export function ShopsEmptyStateB() {
  return (
    <div
      data-testid="empty-state-b"
      className="flex flex-col items-center justify-center py-16"
    >
      <Store size={40} className="text-faint" aria-hidden="true" />
      <h3 className="text-[15px] font-semibold text-ink mt-4">No shops yet</h3>
      <p className="text-[13.5px] text-muted mt-1.5">
        Add your first shop to start managing reviews.
      </p>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("shop:open-create"))}
        className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        + Add your first shop
      </button>
    </div>
  );
}
