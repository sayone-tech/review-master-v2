import { Pencil, Trash2 } from "lucide-react";
import { DataTable } from "../data-table/DataTable";
import { TemplateEmptyState } from "./TemplateEmptyState";
import { useTemplates } from "./useTemplates";
import type { TemplateRow } from "./types";

const PREVIEW_LENGTH = 120;

interface TemplateTableProps {
  rows: TemplateRow[];
  loading: boolean;
  onEdit: (template: TemplateRow) => void;
  onDelete: (template: TemplateRow) => void;
}

export function TemplateTable({ rows, loading, onEdit, onDelete }: TemplateTableProps) {
  const columns = [
    {
      key: "name",
      label: "NAME",
      skeletonWidth: "160px",
      accessor: (row: TemplateRow) => (
        <span className="text-[13.5px] font-semibold text-ink">{row.name}</span>
      ),
    },
    {
      key: "content",
      label: "CONTENT PREVIEW",
      skeletonWidth: "300px",
      accessor: (row: TemplateRow) => (
        <span className="text-[13px] text-muted leading-snug">
          {row.content.length > PREVIEW_LENGTH
            ? `${row.content.slice(0, PREVIEW_LENGTH)}…`
            : row.content}
        </span>
      ),
    },
  ];

  return (
    <DataTable<TemplateRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(r) => String(r.id)}
      emptyState={<TemplateEmptyState />}
      wrapperClassName="bg-white overflow-hidden"
      renderRowActions={(row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => onEdit(row)}
            aria-label={`Edit ${row.name}`}
            className="w-8 h-8 inline-flex items-center justify-center text-subtle hover:text-ink rounded"
          >
            <Pencil size={15} />
          </button>
          <button
            onClick={() => onDelete(row)}
            aria-label={`Delete ${row.name}`}
            className="w-8 h-8 inline-flex items-center justify-center text-subtle hover:text-red rounded"
          >
            <Trash2 size={15} />
          </button>
        </div>
      )}
    />
  );
}

export function TemplateTableWidget({ initialRows }: { initialRows: TemplateRow[] }) {
  const { rows, loading } = useTemplates(initialRows);

  const handleEdit = (template: TemplateRow) => {
    window.dispatchEvent(new CustomEvent("template:open-edit", { detail: template }));
  };

  const handleDelete = (template: TemplateRow) => {
    window.dispatchEvent(new CustomEvent("template:open-delete", { detail: template }));
  };

  return (
    <TemplateTable rows={rows} loading={loading} onEdit={handleEdit} onDelete={handleDelete} />
  );
}
