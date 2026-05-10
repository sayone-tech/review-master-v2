import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { NotifBell } from "../widgets/notif-bell/NotifBell";

const root = document.getElementById("notif-bell-root");
if (root && !root.dataset.mounted) {
  root.dataset.mounted = "1";
  createRoot(root).render(
    <StrictMode>
      <NotifBell />
    </StrictMode>,
  );
}
