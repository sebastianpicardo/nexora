import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, formatNumber, labelize } from "../lib/format";
import InfoHint from "../components/InfoHint";
import StatCard from "../components/StatCard";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  DocumentsIcon,
  DownloadIcon,
  PricesIcon,
  SearchIcon,
  SuppliersIcon,
} from "../components/Icons";

export default function ItemsPage() {
  const { organization } = useAuth();
  const currency = organization?.default_currency || "CLP";
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search.trim()) params.set("search", search.trim());
      if (reviewStatus) params.set("review_status", reviewStatus);
      const data = await api(`/api/items?${params.toString()}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar los precios.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, reviewStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const loadSummary = useCallback(async () => {
    try {
      const data = await api(`/api/items/summary?currency=${encodeURIComponent(currency)}`);
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

  function submitSearch(event) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  function changeStatus(value) {
    setPage(1);
    setReviewStatus(value);
  }

  function changePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  function exportItems(format) {
    const params = new URLSearchParams({ format });
    if (search.trim()) params.set("search", search.trim());
    if (reviewStatus) params.set("review_status", reviewStatus);
    window.open(`/api/exports/items?${params.toString()}`, "_blank", "noopener");
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Histórico normalizado</div>
          <h2 className="title-with-help">
            Precios auditados
            <InfoHint title="Propósito de la pantalla">
              Compara precios unitarios en una unidad base común por proveedor, SKU y fecha. Aquí se
              concentra el histórico que permite detectar alzas y negociar con evidencia.
            </InfoHint>
          </h2>
          <p>
            Precios unitarios llevados a una unidad base comparable por proveedor, SKU y fecha.
          </p>
        </div>
        <span className="counter-chip">{total} ítems</span>
      </section>

      {summary ? (
        <section className="stats-grid">
          <StatCard
            label="Dinero auditado"
            value={formatMoney(summary.audited_spend, summary.currency)}
            detail={`${summary.documents} documentos procesados`}
            tone="brand"
            icon={<PricesIcon />}
          />
          <StatCard
            label="Ítems normalizados"
            value={formatNumber(summary.total_items, 0)}
            detail={`${summary.auto_approved} auto-aprobados · ${summary.pending} por revisar`}
            icon={<DocumentsIcon />}
          />
          <StatCard
            label="Proveedores analizados"
            value={formatNumber(summary.suppliers, 0)}
            detail="Con historial de compras comparable"
            icon={<SuppliersIcon />}
          />
          <StatCard
            label="Confianza promedio"
            value={`${Math.round(Number(summary.avg_confidence || 0) * 100)}%`}
            detail="Calidad de la extracción documental"
            tone={Number(summary.avg_confidence) < 0.75 ? "warning" : "default"}
          />
        </section>
      ) : null}

      <section className="card">
        <div className="filters-row">
          <form className="search-box" onSubmit={submitSearch}>
            <SearchIcon />
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Buscar por SKU o descripción"
            />
            <button type="submit" className="button ghost small">
              Buscar
            </button>
          </form>
          <select
            className="filter-select"
            value={reviewStatus}
            onChange={(event) => changeStatus(event.target.value)}
          >
            <option value="">Todos los estados</option>
            <option value="auto_approved">Auto-aprobados</option>
            <option value="pending">Pendientes</option>
            <option value="approved">Aprobados</option>
            <option value="rejected">Rechazados</option>
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
          <button type="button" className="button ghost" onClick={() => exportItems("xlsx")} title="Descargar el historial filtrado en Excel">
            <DownloadIcon /> Excel
          </button>
          <button type="button" className="button ghost" onClick={() => exportItems("pdf")} title="Descargar el historial filtrado en PDF">
            <DownloadIcon /> PDF
          </button>
        </div>

        {error ? <div className="alert error">{error}</div> : null}

        {loading ? (
          <div className="empty-state">Cargando precios…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-title">Sin resultados</div>
            <p>Procesa un documento o ajusta los filtros de búsqueda.</p>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Proveedor</th>
                    <th>Ítem</th>
                    <th>Precio original</th>
                    <th>Precio normalizado</th>
                    <th>Confianza</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>{formatDate(item.price_date)}</td>
                      <td>{item.supplier_name || "Sin proveedor"}</td>
                      <td>
                        <div className="cell-title">{item.original_description}</div>
                        <div className="cell-sub">
                          {item.sku ? `SKU ${item.sku} · ` : ""}
                          {item.normalized_description}
                        </div>
                      </td>
                      <td>
                        <div>{formatMoney(item.original_unit_price, item.currency)}</div>
                        <div className="cell-sub">por {item.original_unit || "unidad"}</div>
                      </td>
                      <td>
                        <div>{formatMoney(item.normalized_unit_price, item.currency)}</div>
                        <div className="cell-sub">
                          por {item.base_unit || "unidad"}
                          {Number(item.unit_factor) !== 1
                            ? ` · factor ${formatNumber(item.unit_factor, 4)}`
                            : ""}
                        </div>
                      </td>
                      <td>
                        <span
                          className={`confidence ${Number(item.confidence) < 0.75 ? "low" : "ok"}`}
                        >
                          {Math.round(Number(item.confidence) * 100)}%
                        </span>
                      </td>
                      <td>
                        <span className={`badge status-${item.review_status}`}>
                          {labelize(item.review_status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                Página {page} de {totalPages} · {total} ítems
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
    </div>
  );
}
