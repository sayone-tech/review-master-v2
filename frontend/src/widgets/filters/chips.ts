function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${d} ${months[m - 1]}`;
}

export function formatDateChip(from?: string, to?: string): string | null {
  if (from && to) return `Date: ${shortDate(from)} – ${shortDate(to)}`;
  if (from) return `From ${shortDate(from)}`;
  if (to) return `Until ${shortDate(to)}`;
  return null;
}
