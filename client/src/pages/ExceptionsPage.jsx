import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import ExceptionsTable from "../components/ExceptionsTable";
import ResolveExceptionModal from "../components/ResolveExceptionModal";
import { DownloadIcon } from "../components/Icons";

export default function ExceptionsPage() {
  const { canOperate } = useAuth();
  const [exceptions, setExceptions] = useState([]);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
      if (statusFilter) params.set("status", statusFilter);
      const data = await api(`/api/exceptions?${params.toString()}`);
      setExceptions(data.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar las excepciones.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  function handleResolved() {
    setSelected(null);
    load();
  }

  function exportExceptions(format) {
    const params = new URLSearchParams({ format });
    if (statusFilter) params.set("status", statusFilter);
    window.open(`/api/exports/exceptions?${params.toString()}`, "_blank", "noopener");
  }

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
        <span className="counter-chip">{exceptions.length} en esta vista</span>
      </section>

      <section className="card">
        <div className="filters-row">
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="pending">Pendientes</option>
            <option value="">Todas</option>
            <option value="approved">Aprobadas</option>
            <option value="resolved">Corregidas</option>
            <option value="rejected">Rechazadas</option>
          </select>
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
          <ExceptionsTable exceptions={exceptions} onResolve={canOperate ? setSelected : undefined} />
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
