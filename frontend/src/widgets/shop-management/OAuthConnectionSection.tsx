import { useEffect, useRef } from "react";
import { ExternalLink } from "lucide-react";
import { getOAuthResult } from "./api";

export interface OAuthListingsResult {
  state: string;
  listings: Array<{ name: string; address: string; placeId: string }>;
}

interface Props {
  onConnected: (data: OAuthListingsResult) => void;
  onError: (code: "denied" | "auth_error" | "no_listings" | "popup_blocked" | "closed") => void;
}

export function OAuthConnectionSection({ onConnected, onError }: Props) {
  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<number | null>(null);
  const closeWatchRef = useRef<number | null>(null);
  const cleanupRef = useRef<() => void>(() => {});
  const successFiredRef = useRef<boolean>(false);

  useEffect(() => () => cleanupRef.current(), []);

  function handleConnect() {
    // CRITICAL: window.open must be the FIRST statement in the click handler for Safari.
    const popup = window.open(
      "/oauth/google/start/",
      "google-oauth",
      "width=600,height=700",
    );
    if (!popup) {
      onError("popup_blocked");
      return;
    }
    popupRef.current = popup;
    successFiredRef.current = false;

    const messageHandler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const data = event.data as {
        type?: string;
        state?: string;
        listings?: Array<{ name?: string; address?: string; place_id?: string }>;
        code?: string;
      };
      if (
        data?.type === "oauth_listings" &&
        typeof data.state === "string" &&
        Array.isArray(data.listings)
      ) {
        successFiredRef.current = true;
        cleanup();
        onConnected({
          state: data.state,
          listings: data.listings.map((l) => ({
            name: l.name ?? "",
            address: l.address ?? "",
            placeId: l.place_id ?? "",
          })),
        });
      } else if (data?.type === "oauth_error" && typeof data.code === "string") {
        successFiredRef.current = true;
        cleanup();
        onError(data.code as "denied" | "auth_error" | "no_listings");
      }
    };

    // Close watcher: fires every 500ms to detect popup closure.
    // try/catch around .closed silences the COOP warning Chrome logs while the
    // popup is on Google's cross-origin domain (popup is still open — skip).
    // On actual closure: do an immediate Redis poll before timing out, so the
    // fallback path succeeds even when postMessage was blocked by COOP.
    const closeWatch = window.setInterval(() => {
      let isClosed = false;
      try {
        isClosed = popupRef.current?.closed ?? false;
      } catch {
        return; // COOP blocked access — popup still open on cross-origin URL
      }
      if (!isClosed) return;

      if (closeWatchRef.current !== null) {
        window.clearInterval(closeWatchRef.current);
        closeWatchRef.current = null;
      }

      void (async () => {
        if (successFiredRef.current) return; // postMessage already handled it

        // Immediate one-shot poll — bridges the gap when postMessage is blocked
        // by COOP. Also handles error cases (e.g. no_listings) that _render_error
        // now writes to Redis so we surface the right message instead of "closed".
        try {
          const result = await getOAuthResult("");
          const r = result as {
            type?: string;
            state?: string;
            code?: string;
            listings?: Array<{ name?: string; address?: string; place_id?: string }>;
          };
          if (r?.type === "oauth_listings" && r?.state && Array.isArray(r.listings) && r.listings.length > 0) {
            successFiredRef.current = true;
            cleanup();
            onConnected({
              state: r.state,
              listings: r.listings.map((l) => ({
                name: l.name ?? "",
                address: l.address ?? "",
                placeId: l.place_id ?? "",
              })),
            });
            return;
          }
          if (r?.type === "oauth_error" && r?.code) {
            successFiredRef.current = true;
            cleanup();
            onError(r.code as "denied" | "auth_error" | "no_listings");
            return;
          }
        } catch {
          // Redis unavailable or no result yet — fall through to postMessage wait
        }

        // Give the postMessage handler one final window (800ms) before giving up.
        window.setTimeout(() => {
          if (!successFiredRef.current) {
            cleanup();
            onError("closed");
          }
        }, 800);
      })();
    }, 500);
    closeWatchRef.current = closeWatch;

    // Polling fallback via backend Redis key (30s TTL). Only fires when exactly
    // 1 listing is returned — same rule as the callback template's auto-select.
    let elapsed = 0;
    const interval = window.setInterval(() => {
      elapsed += 2000;
      void (async () => {
        try {
          const result = await getOAuthResult("");
          if (result && typeof result === "object") {
            const r = result as {
              type?: string;
              state?: string;
              code?: string;
              listings?: Array<{ name?: string; address?: string; place_id?: string }>;
            };
            if (r.type === "oauth_listings" && r.state && Array.isArray(r.listings) && r.listings.length > 0) {
              successFiredRef.current = true;
              cleanup();
              onConnected({
                state: r.state,
                listings: r.listings.map((l) => ({
                  name: l.name ?? "",
                  address: l.address ?? "",
                  placeId: l.place_id ?? "",
                })),
              });
            } else if (r.type === "oauth_error" && r.code) {
              successFiredRef.current = true;
              cleanup();
              onError(r.code as "denied" | "auth_error" | "no_listings");
            }
          }
        } catch {
          // ignore — polling is best-effort
        }
        if (elapsed >= 30000) {
          if (pollRef.current !== null) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      })();
    }, 2000);
    pollRef.current = interval;

    function cleanup() {
      window.removeEventListener("message", messageHandler);
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      if (closeWatchRef.current !== null) {
        window.clearInterval(closeWatchRef.current);
        closeWatchRef.current = null;
      }
    }
    cleanupRef.current = cleanup;
    window.addEventListener("message", messageHandler);
  }

  return (
    <button
      type="button"
      onClick={handleConnect}
      className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      data-testid="oauth-connect-button"
    >
      <ExternalLink size={14} aria-hidden="true" />
      Connect Google Business Profile
    </button>
  );
}
