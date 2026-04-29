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
        cleanup();
        onConnected({
          listingName: data.listingName,
          address: data.address ?? "",
          placeId: data.placeId,
          state: data.state,
        });
      } else if (data?.type === "oauth_error" && typeof data.code === "string") {
        cleanup();
        const c = data.code as "denied" | "auth_error" | "no_listings";
        onError(c);
      }
    };

    // SHOP-12: detect popup closure (user dismissed before completion).
    // Note: COOP "same-origin-allow-popups" still permits reading popup.closed
    // on a window we opened. Poll every 500ms.
    const closeWatch = window.setInterval(() => {
      if (popupRef.current?.closed) {
        cleanup();
        onError("closed");
      }
    }, 500);
    closeWatchRef.current = closeWatch;

    // Polling fallback: when COOP blocks postMessage from popup -> opener,
    // poll the backend Redis key (keyed by session via the backend).
    // The backend's oauth_result action falls back to request.session["oauth_state"]
    // when no query param is provided, so empty string works here.
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
            if (r.state) {
              cleanup();
              onConnected({
                listingName: r.listings?.[0]?.name ?? "",
                address: r.listings?.[0]?.address ?? "",
                placeId: r.listings?.[0]?.place_id ?? "",
                state: r.state,
              });
            }
          }
        } catch {
          // ignore — polling is best-effort
        }
        if (elapsed >= 30000) {
          cleanup();
          // popup still open or stuck — closeWatch will fire onError("closed") if user closes it
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
