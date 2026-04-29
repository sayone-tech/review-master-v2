import { useEffect, useRef } from "react";
import { CheckCircle, ExternalLink } from "lucide-react";
import { getOAuthResult } from "./api";

export interface OAuthConnectedState {
  listingName: string;
  address: string;
  placeId: string;
  state: string;
}

interface Props {
  onConnected: (data: OAuthConnectedState) => void;
  onError: (code: "denied" | "auth_error" | "no_listings" | "popup_blocked" | "closed") => void;
  connected: OAuthConnectedState | null;
  onChangeConnection: () => void;
}

export function OAuthConnectionSection({ onConnected, onError, connected, onChangeConnection }: Props) {
  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<number | null>(null);
  const closeWatchRef = useRef<number | null>(null);
  const cleanupRef = useRef<() => void>(() => {});
  // Tracks whether a success (postMessage or polling) has already been handled.
  // Used by closeWatch's grace-period timeout to distinguish "user cancelled" from
  // "popup closed itself after success". Cannot use pollRef for this because cleanup()
  // nulls pollRef on both success AND the 30 s polling timeout.
  const successFiredRef = useRef<boolean>(false);

  useEffect(() => () => cleanupRef.current(), []);

  function handleConnect() {
    // CRITICAL: window.open must be the FIRST statement in the click handler for Safari.
    // Do not await anything before this line.
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
        listingName?: string;
        address?: string;
        placeId?: string;
        state?: string;
        code?: string;
      };
      if (
        data?.type === "oauth_success" &&
        data.listingName !== undefined &&
        data.placeId !== undefined &&
        data.state !== undefined
      ) {
        successFiredRef.current = true;
        cleanup();
        onConnected({
          listingName: data.listingName,
          address: data.address ?? "",
          placeId: data.placeId,
          state: data.state,
        });
      } else if (data?.type === "oauth_error" && typeof data.code === "string") {
        successFiredRef.current = true; // treated as "handled" — don't also fire "closed"
        cleanup();
        const c = data.code as "denied" | "auth_error" | "no_listings";
        onError(c);
      }
    };

    // SHOP-12: detect popup closure (user dismissed before completion).
    // Note: COOP "same-origin-allow-popups" on both the main window and the callback
    // page allows reading popup.closed and postMessage to work across the Google
    // redirect. Poll every 500ms.
    // Race guard: the callback template sends postMessage then closes the popup after
    // 50ms. Give the message handler 600ms to fire before treating closure as a user
    // cancellation. Use successFiredRef (not pollRef) as the sentinel — pollRef is
    // nulled by both the success path AND the 30 s polling timeout, making it an
    // unreliable indicator that success hasn't fired yet.
    const closeWatch = window.setInterval(() => {
      if (popupRef.current?.closed) {
        if (closeWatchRef.current !== null) {
          window.clearInterval(closeWatchRef.current);
          closeWatchRef.current = null;
        }
        window.setTimeout(() => {
          if (!successFiredRef.current) {
            cleanup();
            onError("closed");
          }
        }, 600);
      }
    }, 500);
    closeWatchRef.current = closeWatch;

    // Polling fallback: COOP "same-origin-allow-popups" should allow postMessage,
    // but this provides a resilient backstop via a backend Redis key (30 s TTL)
    // written by the OAuth callback view. The oauth_result action falls back to
    // request.session["oauth_state"] when no state param is provided.
    // Only auto-connects when exactly 1 listing is returned — matching the
    // callback template's auto-select logic. Multiple listings are handled by
    // the in-popup picker (the user submits the form; the popup's POST response
    // renders a single-listing template which fires postMessage).
    let elapsed = 0;
    const interval = window.setInterval(() => {
      elapsed += 2000;
      void (async () => {
        try {
          const result = await getOAuthResult("");
          if (result && typeof result === "object" && "state" in result) {
            const r = result as {
              state?: string;
              listings?: Array<{ name?: string; address?: string; place_id?: string }>;
            };
            if (r.state && r.listings?.length === 1) {
              successFiredRef.current = true;
              cleanup();
              onConnected({
                listingName: r.listings[0].name ?? "",
                address: r.listings[0].address ?? "",
                placeId: r.listings[0].place_id ?? "",
                state: r.state,
              });
            }
          }
        } catch {
          // ignore — polling is best-effort
        }
        if (elapsed >= 30000) {
          // Stop polling after 30 s. Do NOT set successFiredRef — if the user then
          // closes the popup, closeWatch should still fire onError("closed").
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

  if (connected) {
    return (
      <div
        className="flex items-start gap-2.5 rounded-md border p-3"
        style={{ backgroundColor: "#F0FDF4", borderColor: "rgba(22,163,74,0.3)" }}
        data-testid="oauth-success-row"
      >
        <CheckCircle
          size={18}
          style={{ color: "#16A34A" }}
          className="mt-0.5 shrink-0"
          aria-hidden="true"
        />
        <div className="flex-1">
          <div className="text-[13.5px] font-semibold text-ink">{connected.listingName}</div>
          <div className="text-[12.5px] text-muted">{connected.address}</div>
        </div>
        <button
          type="button"
          onClick={onChangeConnection}
          className="text-[12.5px] underline hover:opacity-80"
          style={{ color: "#B9860F" }}
        >
          Change connection
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={handleConnect}
      className="inline-flex items-center gap-1.5 rounded-md border border-line bg-white px-3.5 py-2 text-[13.5px] font-medium text-ink hover:bg-line-soft"
      data-testid="oauth-connect-button"
    >
      <ExternalLink size={14} aria-hidden="true" />
      Connect Google Business Profile
    </button>
  );
}
