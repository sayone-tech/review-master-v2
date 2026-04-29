import { Store } from "lucide-react";

export function ShopsEmptyStateB() {
  return (
    <div
      data-testid="empty-state-b"
      className="bg-white border border-line rounded-card p-12 flex flex-col items-center text-center"
    >
      <Store size={32} className="text-muted mb-3" aria-hidden="true" />
      <h3 className="text-[16px] font-semibold text-ink mb-1">No shops yet</h3>
      <p className="text-[13.5px] text-muted mb-4">
        Add your first shop to start managing reviews.
      </p>
      <button
        id="open-create-shop-empty"
        type="button"
        className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        + Add your first shop
      </button>
    </div>
  );
}
