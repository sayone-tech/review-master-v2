import { createRoot } from "react-dom/client";
import { useState } from "react";
import { Modal, ConfirmModal } from "../widgets/modal";
import { DataTable, type DataTableColumn } from "../widgets/data-table";
import { emitToast } from "../lib/toast";

interface DemoRow {
  id: string;
  name: string;
  stores: number;
  status: string;
}

const DEMO_ROWS: DemoRow[] = [
  { id: "1", name: "Acme Retail", stores: 4, status: "Active" },
  { id: "2", name: "Bravo Foods", stores: 7, status: "Active" },
  { id: "3", name: "Charlie Pharmacy", stores: 2, status: "Disabled" },
];

const DEMO_COLUMNS: DataTableColumn<DemoRow>[] = [
  {
    key: "name",
    label: "Organisation",
    accessor: (r) => <strong className="text-ink font-semibold">{r.name}</strong>,
    skeletonWidth: "140px",
  },
  { key: "stores", label: "Stores", accessor: (r) => r.stores, align: "right", skeletonWidth: "40px" },
  { key: "status", label: "Status", accessor: (r) => r.status, skeletonWidth: "64px" },
];

function Showcase() {
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-[18px] font-semibold text-ink mb-3">React widgets</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
          >
            Open modal
          </button>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Open confirm (amber)
          </button>
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-red text-white border border-transparent rounded-md text-[13.5px] font-medium hover:bg-[#B91C1C]"
          >
            Open delete confirm
          </button>
          <button
            type="button"
            onClick={() =>
              emitToast({ kind: "success", title: "Toast fired", msg: "From the showcase page." })
            }
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Fire toast (success)
          </button>
          <button
            type="button"
            onClick={() => emitToast({ kind: "error", title: "Something went wrong", msg: "Try again." })}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Fire toast (error)
          </button>
          <button
            type="button"
            onClick={() => setTableLoading((v) => !v)}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Toggle table loading
          </button>
        </div>
      </section>

      <section>
        <h2 className="text-[18px] font-semibold text-ink mb-3">Data table</h2>
        <DataTable<DemoRow>
          columns={DEMO_COLUMNS}
          rows={DEMO_ROWS}
          loading={tableLoading}
          rowKey={(r) => r.id}
          renderRowActions={(r) => (
            <button
              type="button"
              aria-label={`Open actions for ${r.name}`}
              className="w-7 h-7 rounded-sm text-muted hover:bg-line-soft flex items-center justify-center"
            >
              ⋯
            </button>
          )}
        />
      </section>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create New Organisation"
        subtitle="Enter the organisation details to get started."
        footer={
          <>
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
            >
              Save
            </button>
          </>
        }
      >
        <p className="text-[13.5px] text-muted">Form fields will live here in Phase 2.</p>
      </Modal>

      <ConfirmModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          emitToast({ kind: "success", title: "Organisation disabled" });
        }}
        variant="amber"
        title="Disable organisation?"
        message="The organisation 'Acme Retail' and all its stores will be inaccessible. You can re-enable it later."
        confirmLabel="Disable"
      />

      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => {
          setDeleteOpen(false);
          emitToast({ kind: "success", title: "Organisation deleted" });
        }}
        variant="red"
        title="Delete organisation?"
        message="This will permanently delete 'Acme Retail' and all associated data. This action cannot be undone."
        confirmLabel="Delete"
        requireTypeToConfirm="Acme Retail"
      />
    </div>
  );
}

const container = document.getElementById("showcase-root");
if (container) {
  createRoot(container).render(<Showcase />);
}
