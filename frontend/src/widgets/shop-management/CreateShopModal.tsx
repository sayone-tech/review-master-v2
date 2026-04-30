import { useEffect, useRef, useState } from "react";
import { CheckCircle, Search } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ApiError, createShop } from "./api";
import { emitToast } from "../../lib/toast";
import { OAuthConnectionSection, type OAuthListingsResult } from "./OAuthConnectionSection";
import type { ShopCreatePayload, ShopRow } from "./types";

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

type Listing = { name: string; address: string; placeId: string };
type Step = "connect" | "pick" | "form";

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
  existingPlaceIds?: Set<string>;
}

export function CreateShopModal({ open, onClose, onCreated, regions, existingPlaceIds }: Props) {
  const [step, setStep] = useState<Step>("connect");
  const [oauthState, setOauthState] = useState<string>("");
  const [listings, setListings] = useState<Listing[]>([]);
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [region, setRegion] = useState<number | "">(regions[0]?.id ?? "");
  const [streetAddress, setStreetAddress] = useState("");
  const [errors, setErrors] = useState<Record<string, string | string[]>>({});
  const [submitting, setSubmitting] = useState(false);
  const [listingQuery, setListingQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const filteredListings = listingQuery.trim()
    ? listings.filter(
        (l) =>
          l.name.toLowerCase().includes(listingQuery.toLowerCase()) ||
          l.address.toLowerCase().includes(listingQuery.toLowerCase()),
      )
    : listings;

  function highlight(text: string): React.ReactNode {
    if (!listingQuery.trim()) return text;
    const q = listingQuery.toLowerCase();
    const t = String(text);
    const i = t.toLowerCase().indexOf(q);
    if (i < 0) return text;
    return (
      <>
        {t.slice(0, i)}
        <mark style={{ background: "#FEF08A", color: "inherit", padding: 0, borderRadius: 2 }}>
          {t.slice(i, i + listingQuery.length)}
        </mark>
        {t.slice(i + listingQuery.length)}
      </>
    );
  }

  function reset() {
    setStep("connect");
    setOauthState("");
    setListings([]);
    setSelectedListing(null);
    setOauthError(null);
    setName("");
    setPhone("");
    setRegion(regions[0]?.id ?? "");
    setStreetAddress("");
    setErrors({});
    setSubmitting(false);
    setListingQuery("");
  }

  // Autofocus search when entering the pick step
  useEffect(() => {
    if (step === "pick") {
      setListingQuery("");
      setTimeout(() => searchRef.current?.focus(), 50);
    }
  }, [step]);

  useEffect(() => {
    if (!open) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleOAuthConnected(result: OAuthListingsResult) {
    setOauthState(result.state);
    setListings(result.listings);
    setOauthError(null);
    setStep("pick");
  }

  function handleSelectListing(l: Listing) {
    setSelectedListing(l);
    setName(l.name);
    setStreetAddress(l.address);
    setStep("form");
  }

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
    if (!selectedListing) return;
    setSubmitting(true);
    const payload: ShopCreatePayload = {
      name,
      region: region as number,
      connection_method: "GOOGLE_OAUTH",
      phone,
      street_address: streetAddress,
      place_id: selectedListing.placeId,
      google_refresh_token: oauthState,
    };
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

  const subtitleMap: Record<Step, string> = {
    connect: "Connect your Google Business Profile to get started.",
    pick: "Select the location to connect.",
    form: "Review and save your shop details.",
  };

  const footer = (
    <>
      {step === "pick" && (
        <button
          type="button"
          onClick={() => setStep("connect")}
          className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
        >
          Back
        </button>
      )}
      <button
        type="button"
        onClick={onClose}
        className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
      >
        Cancel
      </button>
      {step === "form" && (
        <button
          type="submit"
          form="create-shop-form"
          disabled={submitting}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
        >
          {submitting ? "Saving…" : "Add Shop"}
        </button>
      )}
    </>
  );

  const nonField = errors.non_field_errors;

  return (
    <Modal
      open={open}
      title="Add Shop"
      subtitle={subtitleMap[step]}
      size="default"
      onClose={onClose}
      footer={footer}
    >
      {/* ── Step 1: Connect ── */}
      {step === "connect" && (
        <div className="flex flex-col items-center py-10 gap-3">
          <OAuthConnectionSection
            onConnected={handleOAuthConnected}
            onError={(code) =>
              setOauthError(OAUTH_ERROR_MESSAGES[code] ?? "Could not complete connection.")
            }
          />
          {oauthError && (
            <p role="alert" data-testid="oauth-error" className="text-[12px]" style={{ color: "#DC2626" }}>
              {oauthError}
            </p>
          )}
        </div>
      )}

      {/* ── Step 2: Pick location ── */}
      {step === "pick" && (
        <div className="flex flex-col gap-2.5">
          {/* Search input */}
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: "#A1A1AA" }}
              aria-hidden="true"
            />
            <input
              ref={searchRef}
              type="text"
              value={listingQuery}
              onChange={(e) => setListingQuery(e.target.value)}
              placeholder="Search by name or address…"
              className="w-full pl-9 pr-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink"
            />
          </div>

          {/* Result count — only when searching */}
          {listingQuery.trim() && (
            <div className="text-[11.5px]" style={{ color: "#71717A" }}>
              {filteredListings.length}{" "}
              {filteredListings.length === 1 ? "match" : "matches"} for{" "}
              <strong style={{ color: "#18181B" }}>"{listingQuery}"</strong>
            </div>
          )}

          {/* Scrollable radio list */}
          <div
            role="radiogroup"
            aria-label="Locations"
            className="bg-white overflow-y-auto"
            style={{
              maxHeight: 280,
              border: "1px solid #E4E4E7",
              borderRadius: 10,
            }}
          >
            {filteredListings.length === 0 ? (
              <div className="py-9 px-4 text-center">
                <div
                  className="mx-auto mb-2.5 flex items-center justify-center"
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 11,
                    background: "#FAFAFA",
                    border: "1px solid #E4E4E7",
                  }}
                >
                  <Search size={18} style={{ color: "#A1A1AA" }} aria-hidden="true" />
                </div>
                <div className="text-[13px] font-semibold text-ink">No matches found</div>
                <div className="text-[12px] mt-1" style={{ color: "#71717A" }}>
                  Try a different search term.
                </div>
              </div>
            ) : (
              filteredListings.map((l, i) => {
                const alreadyAdded = !!(existingPlaceIds && l.placeId && existingPlaceIds.has(l.placeId));
                return (
                  <div
                    key={i}
                    role="radio"
                    aria-checked="false"
                    aria-disabled={alreadyAdded}
                    tabIndex={alreadyAdded ? -1 : 0}
                    onClick={alreadyAdded ? undefined : () => handleSelectListing(l)}
                    onKeyDown={alreadyAdded ? undefined : (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleSelectListing(l);
                      }
                    }}
                    className={`flex items-center gap-3 transition-colors ${alreadyAdded ? "cursor-not-allowed" : "cursor-pointer hover:bg-[#FAFAFA]"}`}
                    style={{
                      padding: "12px 14px",
                      borderLeft: "3px solid transparent",
                      borderBottom:
                        i < filteredListings.length - 1 ? "1px solid #F4F4F5" : "none",
                      opacity: alreadyAdded ? 0.55 : 1,
                    }}
                  >
                    {/* Radio circle */}
                    <div
                      className="shrink-0 flex items-center justify-center"
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        border: "1.5px solid #D4D4D8",
                        background: "#fff",
                      }}
                      aria-hidden="true"
                    />
                    {/* Name + address */}
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-semibold text-ink leading-snug">
                        {highlight(l.name)}
                      </div>
                      {l.address && (
                        <div
                          className="text-[12px] mt-px"
                          style={{ color: "#71717A", lineHeight: 1.45 }}
                        >
                          {highlight(l.address)}
                        </div>
                      )}
                    </div>
                    {/* Already connected badge */}
                    {alreadyAdded && (
                      <span
                        className="shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full"
                        style={{ background: "#F0FDF4", color: "#16A34A", border: "1px solid rgba(22,163,74,0.25)" }}
                      >
                        Connected
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ── Step 3: Form ── */}
      {step === "form" && (
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

          {/* Connected listing pill */}
          <div
            className="flex items-center gap-2.5 rounded-md border p-3"
            style={{ backgroundColor: "#F0FDF4", borderColor: "rgba(22,163,74,0.3)" }}
          >
            <CheckCircle
              size={16}
              style={{ color: "#16A34A" }}
              className="shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-semibold text-ink truncate">{selectedListing?.name}</div>
              {selectedListing?.address && (
                <div className="text-[12.5px] text-muted truncate">{selectedListing.address}</div>
              )}
            </div>
            <button
              type="button"
              onClick={() => setStep("pick")}
              className="text-[12px] underline shrink-0 hover:opacity-80"
              style={{ color: "#B9860F" }}
            >
              Change
            </button>
          </div>

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
        </form>
      )}
    </Modal>
  );
}
