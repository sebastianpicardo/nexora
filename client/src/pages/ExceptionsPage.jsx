import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import ExceptionsTable from "../components/ExceptionsTable";
import ResolveExceptionModal from "../components/ResolveExceptionModal";
import { ArrowLeftIcon, ArrowRightIcon, DownloadIcon } from "../components/Icons";

export default function ExceptionsPage() {
  const { canOperate } = useAuth();
  const [exceptions, setExceptions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (statusFilter) params.set("status", statusFilter);
      const data = await api(`/api/exceptions?${params.toString()}`);
      setExceptions(data.items || []);
      setTotal(data.total || 0);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar las excepciones.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  function handleResolved() {
    setSelected(null);
    load();
  }

  function changeStatus(value) {
    setPage(1);
    setStatusFilter(value);
  }

  function changePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  function exportExceptions(format) {
    const params = new URLSearchParams({ format });
    if (statusFilter) params.set("status", statusFilter);
    window.open(`/api/exports/exceptions?${params.toString()}`, "_blank", "noopener");
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Human-in-the-Loop</div>
          <h2>Bandeja de excepciones</h2>
          <p>
            Cada alerta incluye la evidencia extraída, el histórico utilizado y la acción aplicada
            sobre el ítem.
          </p>
        </div>
        <span className="counter-chip">{total} en total</span>
      </section>

      <section className="card">
        <div className="filters-row">
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
          >
            <option value="pending">Pendientes</option>
            <option value="">Todas</option>
            <option value="approved">Aprobadas</option>
            <option value="resolved">Corregidas</option>
            <option value="rejected">Rechazadas</option>
          </select>
          <label className="page-size">
            <span>Por página</span>
            <select value={pageSize} onChange={(event) => changePageSize(event.target.value)}>
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </label>
          <button type="button" className="button ghost" onClick={load}>
            Actualizar
          </button>
          <button type="button" className="button ghost" onClick={() => exportExceptions("xlsx")}>
            <DownloadIcon /> Excel
          </button>
          <button type="button" className="button ghost" onClick={() => exportExceptions("pdf")}>
            <DownloadIcon /> PDF
          </button>
        </div>

        {error ? <div className="alert error">{error}</div> : null}

        {loading ? (
          <div className="empty-state">Cargando excepciones…</div>
        ) : (
          <>
            <ExceptionsTable exceptions={exceptions} onResolve={canOperate ? setSelected : undefined} />
            <div className="pagination">
              <button
                type="button"
                className="button ghost small"
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                <ArrowLeftIcon /> Anterior
              </button>
              <span>
                Página {page} de {totalPages} · {total} excepciones
              </span>
              <button
                type="button"
                className="button ghost small"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                Siguiente <ArrowRightIcon />
              </button>
            </div>
          </>
        )}
      </section>

      {selected && canOperate ? (
        <ResolveExceptionModal
          key={selected.id}
          exception={selected}
          onClose={() => setSelected(null)}
          onResolved={handleResolved}
        />
      ) : null}
    </div>
  );
}
