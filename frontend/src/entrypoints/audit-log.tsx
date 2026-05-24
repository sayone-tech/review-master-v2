// Phase 21-04 — Audit log entrypoint.
// Mounts the AuditLogWidget into #audit-log-root from templates/org-admin/audit-log.html.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuditLogWidget } from "../widgets/audit-log/AuditLogWidget";
import type { ActorOption } from "../widgets/audit-log/types";

function readJson<T>(elementId: string, fallback: T): T {
  const el = document.getElementById(elementId);
  if (!el || !el.textContent) return fallback;
  try {
    return JSON.parse(el.textContent) as T;
  } catch {
    return fallback;
  }
}

function mount() {
  const root = document.getElementById("audit-log-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const userRole = root.dataset.userRole ?? "STAFF_ADMIN";
  const actors = readJson<ActorOption[]>("audit-log-actors-data", []);
  createRoot(root).render(
    <StrictMode>
      <AuditLogWidget userRole={userRole} actors={actors} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
