import { MapPin } from "lucide-react";

export function RegionEmptyState() {
  const handleClick = () => {
    window.dispatchEvent(new CustomEvent("region:open-create"));
  };

  return (
    <div
      className="flex flex-col items-center justify-center py-16"
      data-testid="regions-empty-state"
    >
      <MapPin size={40} className="text-faint" />
      <h3 className="text-[15px] font-semibold text-ink mt-4">No regions yet</h3>
      <p className="text-[13.5px] text-muted mt-1.5">
        Regions help you organise your shops by area or location.
      </p>
      <button
        id="open-create-region-empty"
        onClick={handleClick}
        className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        Create your first region
      </button>
    </div>
  );
}
