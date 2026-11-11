import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, formatNumber, labelize, percent } from "../lib/format";
import StatCard from "../components/StatCard";
import { ClockIcon, DocumentsIcon, PricesIcon, SparkIcon } from "../components/Icons";

const HISTORY_OPTIONS = [3, 6, 9, 12];
const HORIZON_OPTIONS = [1, 2, 3];

const TREND_TONES = {
  sube_fuerte: "status-rejected",
  sube: "priority-high",
  baja_fuerte: "status-approved",
  baja: "status-approved",
  estable: "status-pending",
};

export default function ForecastPage() {
  const { organization } = useAuth();
  const [currency, setCurrency] = useState(organization?.default_currency || "CLP");
  const [historyMonths, setHistoryMonths] = useState(6);
  const [horizon, setHorizon] = useState(1);
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
        history_months: String(historyMonths),
        horizon: String(horizon),
      });
      const result = await api(`/api/insights/forecast?${params.toString()}`);
      setData(result);
    } catch (err) {
      setError(err.message || "No se pudo calcular el pronóstico.");
    } finally {
      setLoading(false);
    }
  }, [currency, historyMonths, horizon]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = data?.summary || {};
  const items = data?.items || [];

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><ClockIcon /> Planificación</div>
          <h2>Pronóstico de compras</h2>
          <p>
            Proyecta consumo y gasto futuro a partir de tu historial, con tendencia por producto
            para anticipar reposiciones y negociaciones.
          </p>
        </div>
        <div className="card-head-tools">
          <label className="page-size">
            <span>Historial</span>
            <select value={historyMonths} onChange={(event) => setHistoryMonths(Number(event.target.value))}>
              {HISTORY_OPTIONS.map((option) => (
                <option key={option} value={option}>{option} meses</option>
              ))}
            </select>
          </label>
          <label className="page-size">
            <span>Horizonte</span>
            <select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>
              {HORIZON_OPTIONS.map((option) => (
                <option key={option} value={option}>{option} mes(es)</option>
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
          label={`Gasto proyectado (${horizon} mes${horizon > 1 ? "es" : ""})`}
          value={formatMoney(summary.projected_spend || 0, currency)}
          detail={`Basado en ${historyMonths} meses de historial`}
          tone="brand"
          icon={<PricesIcon />}
        />
        <StatCard
          label="Productos analizados"
          value={loading ? "—" : summary.products ?? 0}
          detail="Con consumo registrado"
          icon={<DocumentsIcon />}
        />
        <StatCard
          label="Productos al alza"
          value={loading ? "—" : summary.products_rising ?? 0}
          detail="Tendencia de consumo creciente"
          tone="warning"
          icon={<SparkIcon />}
        />
        <StatCard
          label="Productos a la baja"
          value={loading ? "—" : summary.products_falling ?? 0}
          detail="Tendencia de consumo decreciente"
          tone="ok"
          icon={<ClockIcon />}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Próximas compras</h2>
            <p>Cantidad y gasto proyectado por producto según tendencia reciente.</p>
          </div>
          <span className="badge">{items.length} producto(s)</span>
        </div>
        {loading ? (
          <div className="empty-state">Calculando pronóstico de consumo…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p>Necesitas al menos dos meses de historial para generar pronósticos.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Promedio mensual</th>
                  <th>Últimos meses</th>
                  <th>Tendencia</th>
                  <th>Cantidad proyectada</th>
                  <th>Costo unitario</th>
                  <th>Gasto proyectado</th>
                  <th>Última compra</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={`${row.product_key}-${row.base_unit || ""}`}>
                    <td>
                      <strong>{row.description || row.product_key}</strong>
                      <div className="muted small">{row.base_unit || "unidad"}</div>
                    </td>
                    <td>{formatNumber(row.avg_monthly_quantity, 2)}</td>
                    <td>{formatNumber(row.recent_monthly_quantity, 2)}</td>
                    <td>
                      <span className={`badge ${TREND_TONES[row.trend] || ""}`}>
                        {labelize(row.trend)} {percent(row.trend_pct, 1)}
                      </span>
                    </td>
                    <td>{formatNumber(row.projected_quantity, 2)}</td>
                    <td className="mono">{formatMoney(row.unit_cost, currency)}</td>
                    <td className="mono">{formatMoney(row.projected_spend, currency)}</td>
                    <td>{formatDate(row.last_purchase)}</td>
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
