export function TemplateEmptyState() {
  return (
    <div className="py-16 text-center">
      <p className="text-[14px] font-medium text-ink mb-1">No reply templates yet</p>
      <p className="text-[13px] text-muted mb-4">
        Create templates to speed up replying to reviews.
      </p>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("template:open-create"))}
        className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        + Create Template
      </button>
    </div>
  );
}
