export function RoleBadge({ role }: { role: "ORG_ADMIN" | "STAFF_ADMIN" }) {
  if (role === "ORG_ADMIN") {
    return (
      <span
        style={{ backgroundColor: "#F3E8FF", color: "#7C3AED" }}
        className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-semibold"
      >
        Manager
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-[2px] rounded-full text-[12px] font-semibold bg-line-soft text-muted">
      Staff
    </span>
  );
}
