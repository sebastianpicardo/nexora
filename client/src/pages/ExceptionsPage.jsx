import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney, formatNumber } from "../lib/format";
import ExceptionsTable from "../components/ExceptionsTable";
import InfoHint from "../components/InfoHint";
import ResolveExceptionModal from "../components/ResolveExceptionModal";
import StatCard from "../components/StatCard";
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  DownloadIcon,
  ExceptionsIcon,
  PricesIcon,
} from "../components/Icons";

export default function ExceptionsPage() {
  const { canOperate, organization } = useAuth();
  const currency = organization?.default_currency || "CLP";
  const [exceptions, setExceptions] = useState([]);
  const [summary, setSummary] = useState(null);
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

  const loadSummary = useCallback(async () => {
    try {
      const data = await api(`/api/exceptions/summary?currency=${encodeURIComponent(currency)}`);
      setSummary(data);
    } catch {
      setSummary(null);
    }
  }, [currency]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  function refresh() {
    load();
    loadSummary();
  }

  function handleResolved() {
    setSelected(null);
    load();
    loadSummary();
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
          <h2 className="title-with-help">
            Bandeja de excepciones
            <InfoHint title="¿Qué es esto?">
              Es tu cola de revisión humana. NEXORA prioriza por severidad los casos donde el precio,
              la unidad o la confianza requieren una decisión antes de afectar tus compras.
            </InfoHint>
          </h2>
          <p>
            Cada alerta incluye la evidencia extraída, el histórico utilizado y la acción aplicada
            sobre el ítem.
          </p>
        </div>
        <span className="counter-chip">{total} en total</span>
      </section>

      {summary ? (
        <section className="stats-grid">
          <StatCard
            label="Excepciones abiertas"
            value={formatNumber(summary.pending, 0)}
            detail={`${summary.total} alertas en el histórico`}
            icon={<ExceptionsIcon />}
          />
          <StatCard
            label="Críticas sin resolver"
            value={formatNumber(summary.critical_pending, 0)}
            detail="Prioridad máxima para el equipo"
            tone="warning"
            icon={<AlertTriangleIcon />}
          />
          <StatCard
            label="Alertas resueltas"
            value={formatNumber(summary.resolved, 0)}
            detail={`${summary.price_alerts} alzas de precio pendientes`}
            icon={<CheckIcon />}
          />
          <StatCard
            label="Ahorro estimado"
            value={formatMoney(summary.estimated_savings, summary.currency)}
            detail={`Exposición potencial: ${formatMoney(summary.potential_exposure, summary.currency)}`}
            tone="brand"
            icon={<PricesIcon />}
          />
        </section>
      ) : null}

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
          <button type="button" className="button ghost" onClick={refresh}>
            Actualizar
          </button>
          <button type="button" className="button ghost" onClick={() => exportExceptions("xlsx")} title="Descargar excepciones filtradas en Excel">
            <DownloadIcon /> Excel
          </button>
          <button type="button" className="button ghost" onClick={() => exportExceptions("pdf")} title="Descargar excepciones filtradas en PDF">
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
