import { MessageSquare, Search, Store } from "lucide-react";

interface EmptyAProps {
  isOrgAdmin: boolean;
}

export function EmptyStateA({ isOrgAdmin }: EmptyAProps) {
  return (
    <div className="p-12 text-center">
      <Store size={40} className="text-faint mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[20px] font-semibold text-ink mb-1">No connected shops yet</h3>
      <p className="text-[14px] text-muted mb-4">
        {isOrgAdmin
          ? "Connect a shop to Google to start syncing reviews."
          : "Ask your administrator to connect a shop."}
      </p>
      {isOrgAdmin && (
        <a
          href="/admin/org/shops/"
          className="inline-block bg-yellow text-black hover:bg-yellow-hover px-4 py-2 text-[14px] font-semibold rounded-md"
        >
          Go to Shops
        </a>
      )}
    </div>
  );
}

export function EmptyStateB() {
  return (
    <div className="p-12 text-center">
      <MessageSquare size={40} className="text-faint mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[20px] font-semibold text-ink mb-1">No reviews yet</h3>
      <p className="text-[14px] text-muted">
        Reviews will appear here once your sync completes.
      </p>
    </div>
  );
}

interface EmptyCProps {
  onClearFilters: () => void;
}

export function EmptyStateC({ onClearFilters }: EmptyCProps) {
  return (
    <div className="p-12 text-center">
      <Search size={40} className="text-faint mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[20px] font-semibold text-ink mb-1">
        No reviews match your filters
      </h3>
      <p className="text-[14px] text-muted mb-4">
        Try adjusting your filters or search terms.
      </p>
      <button
        type="button"
        onClick={onClearFilters}
        className="bg-white text-ink border border-line hover:bg-line-soft px-4 py-2 text-[14px] font-semibold rounded-md"
      >
        Clear Filters
      </button>
    </div>
  );
}

export const ReviewEmptyStates = { EmptyStateA, EmptyStateB, EmptyStateC };
