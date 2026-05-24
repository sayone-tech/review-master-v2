import { useState, useCallback } from "react";
import { Modal } from "../modal/Modal";
import { ApiError, createRegion } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionRow } from "./types";

export function deriveRegionId(name: string, count: number): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const prefix = words
    .slice(0, 4)
    .map((w) => w[0].toUpperCase())
    .join("");
  const suffix = String(count + 1).padStart(3, "0");
  return prefix + suffix;
}

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface CreateRegionModalProps {
  open: boolean;
  regionCount: number;
  onClose: () => void;
  onCreated: (region: RegionRow) => void;
}

export function CreateRegionModal({
  open,
  regionCount,
  onClose,
  onCreated,
}: CreateRegionModalProps) {
  const [name, setName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [autoMode, setAutoMode] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; region_id?: string }>({});

  const reset = useCallback(() => {
    setName("");
    setRegionId("");
    setAutoMode(true);
    setErrors({});
    setSubmitting(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setName(val);
    if (autoMode) {
      setRegionId(deriveRegionId(val, regionCount));
    }
  };

  const handleRegionIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toUpperCase();
    setRegionId(val);
    if (val === "") {
      setAutoMode(true); // RGN-05: resume auto-population when cleared
    } else {
      setAutoMode(false); // RGN-04: stop auto-population on manual edit
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setSubmitting(true);
    try {
      const region = await createRegion({ name, region_id: regionId });
      emitToast({ kind: "success", title: `Region '${region.name}' created.` });
      onCreated(region);
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
      title="Create Region"
      subtitle="Enter a name and ID for the new region."
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
            form="create-region-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting && (
              <span className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
            )}
            Create Region
          </button>
        </>
      }
    >
      <form id="create-region-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="create-region-name" className={labelCls}>
            Region Name
          </label>
          <input
            id="create-region-name"
            type="text"
            value={name}
            onChange={handleNameChange}
            placeholder="e.g. North West"
            className={errors.name ? inputErrorCls : inputCls}
            autoFocus
          />
          {errors.name && (
            <p role="alert" data-testid="error-create-region-name" className="mt-1 text-[12px] text-red">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="create-region-id" className={labelCls}>
            Region ID
          </label>
          <input
            id="create-region-id"
            type="text"
            value={regionId}
            onChange={handleRegionIdChange}
            placeholder="e.g. NW001"
            className={errors.region_id ? inputErrorCls : inputCls}
            data-testid="field-region_id"
            data-auto-mode={String(autoMode)}
          />
          {errors.region_id && (
            <p
              role="alert"
              data-testid="error-create-region-id"
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
