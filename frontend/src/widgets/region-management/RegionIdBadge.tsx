export function RegionIdBadge({ regionId }: { regionId: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-[3px] rounded-[999px] text-[12px] font-normal font-mono bg-line-soft text-muted"
      data-testid="region-id-badge"
    >
      {regionId}
    </span>
  );
}
