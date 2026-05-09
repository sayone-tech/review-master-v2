import { useState, useCallback, useEffect } from "react";
import { Modal } from "../modal/Modal";
import { ApiError, updateTemplate } from "./api";
import { emitToast } from "../../lib/toast";
import type { TemplateRow } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const textareaCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink resize-y min-h-[120px]";
const textareaErrorCls = textareaCls + " border-red";
const labelCls = "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface EditTemplateModalProps {
  open: boolean;
  template: TemplateRow | null;
  onClose: () => void;
  onUpdated: (template: TemplateRow) => void;
}

export function EditTemplateModal({ open, template, onClose, onUpdated }: EditTemplateModalProps) {
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; content?: string }>({});

  useEffect(() => {
    if (template) {
      setName(template.name);
      setContent(template.content);
      setErrors({});
      setSubmitting(false);
    }
  }, [template]);

  const reset = useCallback(() => {
    setName("");
    setContent("");
    setErrors({});
    setSubmitting(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!template) return;
    setErrors({});
    setSubmitting(true);
    try {
      const updated = await updateTemplate(template.id, { name, content });
      emitToast({ kind: "success", title: "Template updated." });
      onUpdated(updated);
      reset();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors(err.data as { name?: string; content?: string });
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
      title="Edit Template"
      subtitle="Update the template name or content."
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
            form="edit-template-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting && (
              <span className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
            )}
            Save Template
          </button>
        </>
      }
    >
      <form id="edit-template-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="edit-template-name" className={labelCls}>
            Template Name
          </label>
          <input
            id="edit-template-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Standard Thank You"
            className={errors.name ? inputErrorCls : inputCls}
            autoFocus
          />
          {errors.name && (
            <p role="alert" className="mt-1 text-[12px] text-red">
              {Array.isArray(errors.name) ? errors.name[0] : errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="edit-template-content" className={labelCls}>
            Content
          </label>
          <textarea
            id="edit-template-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Write your reply template here…"
            className={errors.content ? textareaErrorCls : textareaCls}
          />
          {errors.content && (
            <p role="alert" className="mt-1 text-[12px] text-red">
              {Array.isArray(errors.content) ? errors.content[0] : errors.content}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
