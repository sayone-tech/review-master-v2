import { useState, useCallback, useEffect } from "react";
import { Modal } from "../modal/Modal";
import { ApiError, updateRegion } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionRow } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface EditRegionModalProps {
  open: boolean;
  region: RegionRow | null;
  onClose: () => void;
  onUpdated: (region: RegionRow) => void;
}

export function EditRegionModal({ open, region, onClose, onUpdated }: EditRegionModalProps) {
  const [name, setName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; region_id?: string }>({});

  // Pre-fill fields when region changes
  useEffect(() => {
    if (region) {
      setName(region.name);
      setRegionId(region.region_id);
      setErrors({});
      setSubmitting(false);
    }
  }, [region]);

  const reset = useCallback(() => {
    setName("");
    setRegionId("");
    setErrors({});
    setSubmitting(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  // NO autoMode: typing in Region Name does NOT update Region ID (RGN-08)
  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value);
  };

  const handleRegionIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRegionId(e.target.value.toUpperCase());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!region) return;
    setErrors({});
    setSubmitting(true);
    try {
      const updated = await updateRegion(region.id, { name, region_id: regionId });
      emitToast({ kind: "success", title: "Region updated." });
      onUpdated(updated);
      reset();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors(err.data as { name?: string; region_id?: string });
      } else {
        emitToast({
          kind: "error",
          title: "Something went wrong.",
          msg: "Please try again. If the problem persists, contact support.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Edit Region"
      subtitle="Update the region name or ID."
      size="default"
      onClose={handleClose}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="edit-region-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting && (
              <span className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
            )}
            Save Region
          </button>
        </>
      }
    >
      <form id="edit-region-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="edit-region-name" className={labelCls}>
            Region Name
          </label>
          <input
            id="edit-region-name"
            type="text"
            value={name}
            onChange={handleNameChange}
            placeholder="e.g. North West"
            className={errors.name ? inputErrorCls : inputCls}
            autoFocus
          />
          {errors.name && (
            <p role="alert" data-testid="error-edit-region-name" className="mt-1 text-[12px] text-red">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="edit-region-id" className={labelCls}>
            Region ID
          </label>
          <input
            id="edit-region-id"
            type="text"
            value={regionId}
            onChange={handleRegionIdChange}
            placeholder="e.g. NW001"
            className={errors.region_id ? inputErrorCls : inputCls}
            data-testid="field-region_id"
          />
          {errors.region_id && (
            <p
              role="alert"
              data-testid="error-edit-region-id"
              className="mt-1 text-[12px] text-red"
            >
              {Array.isArray(errors.region_id) ? errors.region_id[0] : errors.region_id}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
