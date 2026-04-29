import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ApiError, createShop } from "./api";
import { emitToast } from "../../lib/toast";
import { OAuthConnectionSection, type OAuthConnectedState } from "./OAuthConnectionSection";
import type { ConnectionMethod, ShopCreatePayload, ShopRow } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  denied: "Permission was not granted.",
  auth_error: "Could not complete connection.",
  no_listings: "No business listings found in this Google account.",
  popup_blocked: "Popup was blocked. Please allow popups for this site.",
  closed: "Connection cancelled. Please try again.",
};

interface RegionLite {
  id: number;
  region_id: string;
  name: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (shop: ShopRow) => void;
  regions: RegionLite[];
}

export function CreateShopModal({ open, onClose, onCreated, regions }: Props) {
  const [method, setMethod] = useState<ConnectionMethod>("GOOGLE_OAUTH");
  const [oauthConnected, setOauthConnected] = useState<OAuthConnectedState | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [region, setRegion] = useState<number | "">(regions[0]?.id ?? "");
  const [placeId, setPlaceId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [streetAddress, setStreetAddress] = useState("");
  const [city, setCity] = useState("");
  const [stateField, setStateField] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [errors, setErrors] = useState<Record<string, string | string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setMethod("GOOGLE_OAUTH");
    setOauthConnected(null);
    setOauthError(null);
    setName("");
    setPhone("");
    setRegion(regions[0]?.id ?? "");
    setPlaceId("");
    setApiKey("");
    setApiKeyVisible(false);
    setStreetAddress("");
    setCity("");
    setStateField("");
    setZipCode("");
    setErrors({});
    setSubmitting(false);
  }

  useEffect(() => {
    if (!open) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Auto-populate Name + Address after OAuth (SHOP-09)
  useEffect(() => {
    if (!oauthConnected) return;
    if (!name) setName(oauthConnected.listingName);
    if (!streetAddress) setStreetAddress(oauthConnected.address);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oauthConnected]);

  function fieldError(key: string): string | undefined {
    const e = errors[key];
    if (!e) return undefined;
    return Array.isArray(e) ? e[0] : String(e);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});
    if (!region) {
      setErrors({ region: ["Region is required."] });
      return;
    }
    if (method === "GOOGLE_OAUTH" && !oauthConnected) {
      setOauthError("Please connect Google Business Profile first.");
      return;
    }
    setSubmitting(true);
    const payload: ShopCreatePayload = {
      name,
      region: region as number,
      connection_method: method,
      phone,
      street_address: streetAddress,
      city,
      state: stateField,
      zip_code: zipCode,
    };
    if (method === "GOOGLE_OAUTH" && oauthConnected) {
      payload.place_id = oauthConnected.placeId;
      // The backend resolves the actual refresh_token from session using the state.
      // We send the state in google_refresh_token field; the backend's perform_create
      // looks up request.session[f"oauth_token:{state}"] to get the real token (SHOP-13).
      payload.google_refresh_token = oauthConnected.state;
    } else if (method === "MANUAL") {
      payload.place_id = placeId;
      payload.api_key = apiKey;
    }
    try {
      const shop = await createShop(payload);
      emitToast({ kind: "success", title: `Shop '${shop.name}' created.` });
      onCreated(shop);
      reset();
      onClose();
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 400 &&
        err.data &&
        typeof err.data === "object"
      ) {
        setErrors(err.data as Record<string, string | string[]>);
      } else {
        emitToast({ kind: "error", title: "Something went wrong.", msg: "Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const nonField = errors.non_field_errors;

  return (
    <Modal
      open={open}
      title="Add Shop"
      subtitle="Connect via Google or enter Place ID and API key manually."
      size="default"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-shop-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting ? "Saving…" : "Add Shop"}
          </button>
        </>
      }
    >
      <form id="create-shop-form" onSubmit={handleSubmit} className="space-y-4" aria-label="Add Shop">
        {nonField && (
          <div
            className="rounded-md border p-2.5 text-[13px]"
            style={{ backgroundColor: "#FEF2F2", borderColor: "rgba(220,38,38,0.3)", color: "#DC2626" }}
            role="alert"
            data-testid="non-field-error"
          >
            {Array.isArray(nonField) ? nonField[0] : nonField}
          </div>
        )}

        {/* Connection method radio */}
        <fieldset className="space-y-2">
          <legend className={labelCls}>Connection method</legend>
          <label className="flex items-center gap-2 text-[13.5px]">
            <input
              type="radio"
              name="method"
              aria-label="Connect with Google"
              checked={method === "GOOGLE_OAUTH"}
              onChange={() => setMethod("GOOGLE_OAUTH")}
            />{" "}
            Connect with Google
          </label>
          <label className="flex items-center gap-2 text-[13.5px]">
            <input
              type="radio"
              name="method"
              aria-label="Enter manually"
              checked={method === "MANUAL"}
              onChange={() => setMethod("MANUAL")}
            />{" "}
            Enter manually
          </label>
        </fieldset>

        {method === "GOOGLE_OAUTH" && (
          <div>
            <OAuthConnectionSection
              connected={oauthConnected}
              onConnected={(d) => {
                setOauthConnected(d);
                setOauthError(null);
              }}
              onError={(code) =>
                setOauthError(
                  OAUTH_ERROR_MESSAGES[code] ?? "Could not complete connection.",
                )
              }
              onChangeConnection={() => setOauthConnected(null)}
            />
            {oauthError && (
              <p role="alert" data-testid="oauth-error" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
                {oauthError}
              </p>
            )}
          </div>
        )}

        {method === "MANUAL" && (
          <>
            <div>
              <label htmlFor="cs-place-id" className={labelCls}>
                Google Place ID
              </label>
              <input
                id="cs-place-id"
                type="text"
                value={placeId}
                onChange={(e) => setPlaceId(e.target.value)}
                className={fieldError("place_id") ? inputErrorCls : inputCls}
                placeholder="ChIJ..."
                aria-label="Google Place ID"
              />
              {fieldError("place_id") && (
                <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
                  {fieldError("place_id")}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="cs-api-key" className={labelCls}>
                Google Places API Key
              </label>
              <div className="relative">
                <input
                  id="cs-api-key"
                  type={apiKeyVisible ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className={fieldError("api_key") ? inputErrorCls : inputCls}
                  aria-label="Google Places API Key"
                />
                <button
                  type="button"
                  onClick={() => setApiKeyVisible(!apiKeyVisible)}
                  aria-label={apiKeyVisible ? "Hide" : "Show"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted"
                >
                  {apiKeyVisible ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {fieldError("api_key") && (
                <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
                  {fieldError("api_key")}
                </p>
              )}
            </div>
          </>
        )}

        {/* Common fields */}
        <div>
          <label htmlFor="cs-name" className={labelCls}>
            Shop Name
          </label>
          <input
            id="cs-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={fieldError("name") ? inputErrorCls : inputCls}
            aria-label="Shop Name"
          />
          {fieldError("name") && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {fieldError("name")}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="cs-region" className={labelCls}>
            Region
          </label>
          <select
            id="cs-region"
            value={region === "" ? "" : String(region)}
            onChange={(e) => setRegion(e.target.value ? Number(e.target.value) : "")}
            className={fieldError("region") ? inputErrorCls : inputCls}
            aria-label="Region"
          >
            <option value="">Select region…</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.region_id})
              </option>
            ))}
          </select>
          {fieldError("region") && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {fieldError("region")}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="cs-phone" className={labelCls}>
            Phone (optional)
          </label>
          <input
            id="cs-phone"
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="cs-street" className={labelCls}>
            Street Address
          </label>
          <input
            id="cs-street"
            type="text"
            value={streetAddress}
            onChange={(e) => setStreetAddress(e.target.value)}
            className={inputCls}
          />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label htmlFor="cs-city" className={labelCls}>
              City
            </label>
            <input
              id="cs-city"
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label htmlFor="cs-state" className={labelCls}>
              State
            </label>
            <input
              id="cs-state"
              type="text"
              value={stateField}
              onChange={(e) => setStateField(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label htmlFor="cs-zip" className={labelCls}>
              ZIP
            </label>
            <input
              id="cs-zip"
              type="text"
              value={zipCode}
              onChange={(e) => setZipCode(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>
      </form>
    </Modal>
  );
}
