import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import { formatMoney } from "../lib/format";
import { DownloadIcon, PricesIcon, SparkIcon } from "./Icons";
import StatCard from "./StatCard";

const MODES = [
  { id: "target", label: "Margen objetivo" },
  { id: "p50", label: "Trasladar 50%" },
  { id: "p75", label: "Trasladar 75%" },
  { id: "p100", label: "Trasladar 100%" },
];

function severityLabel(value) {
  return {
    critical: "Crítico",
    high: "Alto",
    medium: "Medio",
    low: "OK",
  }[value] || value;
}

export default function MarginGuardianPanel() {
  const { canManage } = useAuth();
  const [target, setTarget] = useState(15);
  const [minMargin, setMinMargin] = useState(8);
  const [mode, setMode] = useState("target");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(
        await api(`/api/leaks/margin-guardian?target_margin=${target}&min_margin=${minMargin}`),
      );
    } catch (err) {
      setError(err.message || "No se pudo cargar el guardián de margen.");
    } finally {
      setLoading(false);
    }
  }, [target, minMargin]);

  useEffect(() => {
    load();
  }, [load]);

  const items = data?.items || [];
  const summary = data?.summary || {};
  const visible = useMemo(() => items.filter((item) => item.status !== "ok"), [items]);

  function suggestedFor(item) {
    if (mode === "target") return item.suggested_sale;
    return item.pass_through?.[mode] ?? item.suggested_sale;
  }

  async function applyPrice(item) {
    const price = suggestedFor(item);
    if (!price) return;
    setBusy(item.id);
    setError("");
    setNotice("");
    try {
      await api(`/api/price-catalog/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ sale_price: price }),
      });
      setNotice(`Precio de ${item.name} actualizado a ${formatMoney(price, summary.currency)}.`);
      await load();
    } catch (err) {
      setError(err.message || "No se pudo actualizar el precio.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page-stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Guardián de margen y precio sugerido</h2>
            <p>
              Cruza la última alza de costo detectada con tu catálogo y calcula cuánto deberías
              cobrar para proteger el margen.
            </p>
          </div>
          <div className="card-head-tools">
            <label className="page-size">
              <span>Margen objetivo</span>
              <input
                type="number"
                min="0"
                max="90"
                value={target}
                onChange={(event) => setTarget(Number(event.target.value))}
              />
            </label>
            <label className="page-size">
              <span>Mínimo</span>
              <input
                type="number"
                min="0"
                max="90"
                value={minMargin}
                onChange={(event) => setMinMargin(Number(event.target.value))}
              />
            </label>
            <button
              type="button"
              className="button ghost small"
              onClick={() => downloadFile("/api/leaks/margin-guardian.csv?only_changes=true", "precios_sugeridos.csv")}
            >
              <DownloadIcon /> CSV POS/ERP
            </button>
          </div>
        </div>

        {error ? <div className="alert error">{error}</div> : null}
        {notice ? <div className="alert success">{notice}</div> : null}

        <div className="stats-grid">
          <StatCard
            label="Productos en riesgo"
            value={loading && !data ? "—" : summary.at_risk || 0}
            detail={`${summary.items_total || 0} productos en catálogo`}
            tone="warning"
            icon={<PricesIcon />}
          />
          <StatCard
            label="Bajo el costo"
            value={summary.below_cost || 0}
            detail="Requieren corrección inmediata"
            tone="brand"
            icon={<SparkIcon />}
          />
          <StatCard
            label="Alzas de costo"
            value={summary.cost_increases || 0}
            detail="Sobre 3% en el último registro"
            icon={<PricesIcon />}
          />
          <StatCard
            label="Recuperación por unidad"
            value={formatMoney(summary.recovery_per_unit || 0, summary.currency)}
            detail="Si aplicas el precio sugerido"
            tone="ok"
            icon={<SparkIcon />}
          />
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Precio sugerido por producto</h2>
            <p>Elige cómo trasladar el alza de costo antes de actualizar.</p>
          </div>
          <div className="segmented">
            {MODES.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`chip ${mode === option.id ? "active" : ""}`}
                onClick={() => setMode(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {visible.length === 0 && !loading ? (
          <div className="audit-empty">
            <SparkIcon />
            <h3>Márgenes bajo control</h3>
            <p>No hay productos bajo el umbral ni alzas relevantes de costo.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="right">Costo anterior</th>
                  <th className="right">Costo actual</th>
                  <th className="right">Variación</th>
                  <th className="right">Venta</th>
                  <th className="right">Margen</th>
                  <th className="right">Sugerido</th>
                  <th>Estado</th>
                  {canManage ? <th /> : null}
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.name}</strong>
                      <div className="muted small">
                        {item.sku} · {item.unit}{item.supplier ? ` · ${item.supplier}` : ""}
                      </div>
                    </td>
                    <td className="right mono">{formatMoney(item.cost_previous, summary.currency)}</td>
                    <td className="right mono">{formatMoney(item.cost_current, summary.currency)}</td>
                    <td className="right">
                      <span className={`badge ${item.cost_change_pct > 0 ? "severity-medium" : ""}`}>
                        {item.cost_change_pct > 0 ? "+" : ""}
                        {item.cost_change_pct}%
                      </span>
                    </td>
                    <td className="right mono">{formatMoney(item.sale_price, summary.currency)}</td>
                    <td className="right">{item.margin_pct}%</td>
                    <td className="right mono">
                      {formatMoney(suggestedFor(item), summary.currency)}
                    </td>
                    <td>
                      <span className={`badge severity-${item.severity}`}>
                        {severityLabel(item.severity)}
                      </span>
                      <div className="muted small">{item.status_label}</div>
                    </td>
                    {canManage ? (
                      <td>
                        <button
                          type="button"
                          className="button ghost small"
                          disabled={busy === item.id}
                          onClick={() => applyPrice(item)}
                        >
                          {busy === item.id ? "Guardando…" : "Aplicar precio"}
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data?.note ? <p className="muted small">{data.note}</p> : null}
      </section>
    </div>
  );
}
