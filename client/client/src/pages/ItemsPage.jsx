import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate, formatMoney, formatNumber, labelize } from "../lib/format";
import { DownloadIcon, SearchIcon } from "../components/Icons";

export default function ItemsPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100" });
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
  }, [search, reviewStatus]);

  useEffect(() => {
    load();
  }, [load]);

  function submitSearch(event) {
    event.preventDefault();
    setSearch(searchInput);
  }

  function exportItems(format) {
    const params = new URLSearchParams({ format });
    if (search.trim()) params.set("search", search.trim());
    if (reviewStatus) params.set("review_status", reviewStatus);
    window.open(`/api/exports/items?${params.toString()}`, "_blank", "noopener");
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Histórico normalizado</div>
          <h2>Precios auditados</h2>
          <p>
            Precios unitarios llevados a una unidad base comparable por proveedor, SKU y fecha.
          </p>
        </div>
        <span className="counter-chip">{total} ítems</span>
      </section>

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
            onChange={(event) => setReviewStatus(event.target.value)}
          >
            <option value="">Todos los estados</option>
            <option value="auto_approved">Auto-aprobados</option>
            <option value="pending">Pendientes</option>
            <option value="approved">Aprobados</option>
            <option value="rejected">Rechazados</option>
          </select>
          <button type="button" className="button ghost" onClick={load}>
            Actualizar
          </button>
          <button type="button" className="button ghost" onClick={() => exportItems("xlsx")}>
            <DownloadIcon /> Excel
          </button>
          <button type="button" className="button ghost" onClick={() => exportItems("pdf")}>
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
        )}
      </section>
    </div>
  );
}
