import { Pencil, Trash2 } from "lucide-react";
import { DataTable } from "../data-table/DataTable";
import { RegionIdBadge } from "./RegionIdBadge";
import { RegionEmptyState } from "./RegionEmptyState";
import { useRegions } from "./useRegions";
import type { RegionRow } from "./types";

interface RegionTableProps {
  rows: RegionRow[];
  loading: boolean;
  onEdit: (region: RegionRow) => void;
  onDelete: (region: RegionRow) => void;
}

export function RegionTable({ rows, loading, onEdit, onDelete }: RegionTableProps) {
  const columns = [
    {
      key: "name",
      label: "REGION NAME",
      skeletonWidth: "140px",
      accessor: (row: RegionRow) => (
        <span className="text-[13.5px] font-normal text-ink">{row.name}</span>
      ),
    },
    {
      key: "region_id",
      label: "REGION ID",
      skeletonWidth: "80px",
      accessor: (row: RegionRow) => <RegionIdBadge regionId={row.region_id} />,
    },
  ];

  return (
    <DataTable<RegionRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(r) => String(r.id)}
      emptyState={<RegionEmptyState />}
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

export function RegionTableWidget({ initialRows }: { initialRows: RegionRow[] }) {
  const { rows, loading } = useRegions(initialRows);

  const handleEdit = (region: RegionRow) => {
    window.dispatchEvent(new CustomEvent("region:open-edit", { detail: region }));
  };

  const handleDelete = (region: RegionRow) => {
    window.dispatchEvent(new CustomEvent("region:open-delete", { detail: region }));
  };

  return <RegionTable rows={rows} loading={loading} onEdit={handleEdit} onDelete={handleDelete} />;
}
