import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, formatNumber, percent } from "../lib/format";
import StatCard from "../components/StatCard";
import { DollarIcon, ExceptionsIcon, PricesIcon, SuppliersIcon } from "../components/Icons";

const DAY_OPTIONS = [30, 60, 90, 180, 365];
const OVERPRICE_OPTIONS = [5, 10, 15, 20, 30];

export default function OpportunitiesPage() {
  const { organization } = useAuth();
  const [currency, setCurrency] = useState(organization?.default_currency || "CLP");
  const [days, setDays] = useState(90);
  const [minOverprice, setMinOverprice] = useState(10);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (organization?.default_currency) setCurrency(organization.default_currency);
  }, [organization?.default_currency]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        currency,
        days: String(days),
        min_overprice_pct: String(minOverprice),
      });
      const result = await api(`/api/insights/opportunities?${params.toString()}`);
      setData(result);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las oportunidades.");
    } finally {
      setLoading(false);
    }
  }, [currency, days, minOverprice]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = data?.summary || {};
  const items = data?.items || [];

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><DollarIcon /> Inteligencia de precios</div>
          <h2>Oportunidades de ahorro</h2>
          <p>
            Detectamos automáticamente ítems pagados por sobre la mediana histórica y el mejor
            precio registrado por proveedor.
          </p>
        </div>
        <div className="card-head-tools">
          <label className="page-size">
            <span>Ventana</span>
            <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
              {DAY_OPTIONS.map((option) => (
                <option key={option} value={option}>{option} días</option>
              ))}
            </select>
          </label>
          <label className="page-size">
            <span>Sobreprecio mín.</span>
            <select value={minOverprice} onChange={(event) => setMinOverprice(Number(event.target.value))}>
              {OVERPRICE_OPTIONS.map((option) => (
                <option key={option} value={option}>{option}%</option>
              ))}
            </select>
          </label>
          <label className="page-size">
            <span>Moneda</span>
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              {["CLP", "USD", "EUR", "PEN", "COP", "MXN", "BRL", "ARS"].map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <section className="stats-grid">
        <StatCard
          label="Ahorro potencial"
          value={formatMoney(summary.total_potential_savings || 0, currency)}
          detail="Contra el mejor precio histórico"
          tone="ok"
          icon={<DollarIcon />}
        />
        <StatCard
          label="Ítems sobrevalorados"
          value={loading ? "—" : summary.opportunities ?? 0}
          detail={`Umbral ${minOverprice}% sobre la mediana`}
          tone="warning"
          icon={<ExceptionsIcon />}
        />
        <StatCard
          label="Sobreprecio total"
          value={formatMoney(summary.total_excess_cost || 0, currency)}
          detail="Diferencia contra la mediana"
          icon={<PricesIcon />}
        />
        <StatCard
          label="Proveedores afectados"
          value={loading ? "—" : summary.suppliers_affected ?? 0}
          detail="Con oportunidades detectadas"
          icon={<SuppliersIcon />}
        />
      </section>

      {data?.top_suppliers?.length ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Proveedores con mayor oportunidad</h2>
              <p>Concentración del ahorro potencial por proveedor.</p>
            </div>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Proveedor</th>
                  <th>Ahorro potencial</th>
                </tr>
              </thead>
              <tbody>
                {data.top_suppliers.map((row, index) => (
                  <tr key={row.supplier_name}>
                    <td>{index + 1}</td>
                    <td><strong>{row.supplier_name}</strong></td>
                    <td className="mono">{formatMoney(row.potential_savings, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Oportunidades detectadas</h2>
            <p>Comparación contra la mediana histórica y el mejor precio por proveedor.</p>
          </div>
          <span className="badge">{items.length} ítem(s)</span>
        </div>
        {loading ? (
          <div className="empty-state">Analizando historial de precios…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p>No se detectaron sobreprecios con los filtros actuales.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Proveedor</th>
                  <th>Precio actual</th>
                  <th>Mediana</th>
                  <th>Mejor precio</th>
                  <th>Sobreprecio</th>
                  <th>Ahorro potencial</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.normalized_description || row.original_description}</strong>
                      <div className="muted small">
                        {row.sku ? `${row.sku} · ` : ""}{row.base_unit || "unidad"}
                      </div>
                    </td>
                    <td>
                      {row.supplier_name || "—"}
                      {row.best_supplier_name && row.best_supplier_name !== row.supplier_name ? (
                        <div className="muted small">Mejor: {row.best_supplier_name}</div>
                      ) : null}
                    </td>
                    <td className="mono">{formatMoney(row.current_price, currency)}</td>
                    <td className="mono">{formatMoney(row.median_price, currency)}</td>
                    <td className="mono">{formatMoney(row.best_price, currency)}</td>
                    <td>
                      <span className={`badge ${row.overprice_pct >= 30 ? "status-rejected" : "priority-high"}`}>
                        {percent(row.overprice_pct, 1)}
                      </span>
                    </td>
                    <td className="mono">{formatMoney(row.potential_savings, currency)}</td>
                    <td>{formatDate(row.price_date)}</td>
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
