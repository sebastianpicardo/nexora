import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney, formatMonth, formatNumber, percent } from "../lib/format";
import StatCard from "../components/StatCard";
import DemoDataBanner from "../components/DemoDataBanner";
import ActionEmptyState from "../components/ActionEmptyState";
import { ArrowRightIcon, CheckIcon, DollarIcon, PricesIcon, SparkIcon } from "../components/Icons";

const MONTH_OPTIONS = [3, 6, 12, 24];

export default function AnalyticsPage({ onNavigate, embedded = false, onUpload }) {
  const { organization } = useAuth();
  const [currency, setCurrency] = useState(organization?.default_currency || "CLP");
  const [months, setMonths] = useState(6);
  const [data, setData] = useState(null);
  const [verified, setVerified] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [demoNotice, setDemoNotice] = useState("");

  useEffect(() => {
    if (organization?.default_currency) setCurrency(organization.default_currency);
  }, [organization?.default_currency]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ currency, months: String(months) });
      const [overviewResult, verifiedResult] = await Promise.allSettled([
        api(`/api/insights/overview?${params.toString()}`),
        api("/api/insights/savings/verified"),
      ]);
      if (overviewResult.status === "rejected") throw overviewResult.reason;
      setData(overviewResult.value);
      setVerified(verifiedResult.status === "fulfilled" ? verifiedResult.value : null);
    } catch (err) {
      setError(err.message || "No se pudo cargar la analítica.");
    } finally {
      setLoading(false);
    }
  }, [currency, months]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDemoLoaded = useCallback(async () => {
    await load();
    setDemoNotice(
      "Datos de ejemplo cargados: 90 días de compras demo con proveedores, precios y márgenes ya disponibles en las métricas.",
    );
  }, [load]);

  const analytics = data?.analytics;
  const summary = analytics?.summary || {};
  const monthly = analytics?.monthly || [];
  const maxSpend = Math.max(1, ...monthly.map((row) => Number(row.spend) || 0));
  const opportunities = data?.opportunities?.summary || {};
  const forecast = data?.forecast?.summary || {};
  const approvals = data?.approvals?.summary || {};
  const hasData = !loading && ((summary.items ?? 0) > 0 || monthly.length > 0);
  const lowData = !loading && hasData && monthly.length < 2;
  const noSavings = !loading && hasData && Number(opportunities.total_potential_savings || 0) <= 0;
  const noForecast = !loading && hasData && Number(forecast.projected_spend || 0) <= 0;
  const needsDemo = lowData || noSavings || noForecast;
  const savingsDetail =
    (opportunities.opportunities ?? 0) > 0
      ? `${opportunities.opportunities} oportunidad(es) para recuperar`
      : "Aún sin sobrecostos: requiere compras repetidas del mismo producto en distintos documentos";
  const forecastDetail =
    Number(forecast.projected_spend || 0) > 0
      ? `Próximo mes · ${forecast.products_rising ?? 0} producto(s) al alza`
      : "Requiere al menos 3 meses de historial del mismo producto para proyectar";

  return (
    <div className="page-stack">
      <section className={`page-intro ${embedded ? "page-intro-embedded" : ""}`}>
        <div className={embedded ? "sr-only" : undefined}>
          <div className="eyebrow"><SparkIcon /> Analítica ejecutiva</div>
          <h2>Controla el gasto y los precios</h2>
          <p>
            Detecta alzas, entiende tu gasto y prioriza ahorros sin revisar planillas.
          </p>
        </div>
        <div className="card-head-tools">
          <label className="page-size">
            <span>Período</span>
            <select value={months} onChange={(event) => setMonths(Number(event.target.value))}>
              {MONTH_OPTIONS.map((option) => (
                <option key={option} value={option}>{option} meses</option>
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

      {error ? (
        <div className="alert error">
          <span>{error}</span>
          <button type="button" className="button ghost small" onClick={load}>
            Reintentar
          </button>
        </div>
      ) : null}

      {demoNotice ? (
        <div className="alert success">
          <span>{demoNotice}</span>
          <button type="button" className="button ghost small" onClick={() => setDemoNotice("")}>
            Cerrar
          </button>
        </div>
      ) : null}

      {data?.warnings?.length ? (
        <div className="alert warning">
          <span>{data.warnings.join(" ")}</span>
          <button type="button" className="button ghost small" onClick={load}>
            Reintentar
          </button>
        </div>
      ) : null}

      {!loading && !hasData ? (
        <ActionEmptyState
          icon={<PricesIcon />}
          title={error ? "No pudimos cargar la analítica" : "Tu analítica empieza con la primera factura"}
          description={
            error
              ? "El resto de NEXORA sigue disponible. Reintenta o carga el ejemplo de ferretería de 90 días para revisar la vista con datos."
              : "Sube una factura para ver gasto, precios y ahorro potencial sin planillas. También puedes explorar la vista completa con datos de demostración."
          }
          onUpload={onUpload}
          onLoaded={handleDemoLoaded}
        />
      ) : null}

      {needsDemo ? (
        <DemoDataBanner
          compact
          title={
            lowData
              ? "Aún hay pocos meses para comparar"
              : noSavings && noForecast
                ? "Faltan datos para detectar ahorro y proyectar"
                : noSavings
                  ? "Aún no se detectan sobrecostos"
                  : "Aún no hay gasto proyectado"
          }
          description={
            lowData
              ? "Con dos o más meses de historial podrás ver tendencias más confiables. También puedes cargar datos demo para explorar la vista completa."
              : noSavings && noForecast
                ? "Para detectar ahorro se necesitan compras repetidas del mismo producto en distintos documentos; para proyectar, al menos 3 meses de historial. También puedes cargar el ejemplo de 90 días."
                : noSavings
                  ? "Aún sin sobrecostos: requiere compras repetidas del mismo producto en distintos documentos. También puedes cargar el ejemplo de 90 días."
                  : "Requiere al menos 3 meses de historial del mismo producto para proyectar. También puedes cargar el ejemplo de 90 días."
          }
          onLoaded={handleDemoLoaded}
        />
      ) : null}

      {!loading && !hasData ? null : (
        <>
      <section className="stats-grid analytics-stats">
        <StatCard
          label="Índice de precios"
          value={loading ? "—" : formatNumber(summary.price_index ?? 100, 1)}
          detail={`${formatNumber(summary.price_change_pct || 0, 2)}% vs inicio del período`}
          tone={(summary.price_change_pct || 0) > 0 ? "warning" : "ok"}
          icon={<PricesIcon />}
          trend={summary.price_change_pct || 0}
          trendHint="var. período"
        />
        <StatCard
          label="Productos monitoreados"
          value={loading ? "—" : summary.products ?? 0}
          detail={`${summary.suppliers ?? 0} proveedores · ${summary.items ?? 0} ítems`}
          icon={<DollarIcon />}
        />
        <StatCard
          label="Ahorro detectado"
          value={formatMoney(opportunities.total_potential_savings || 0, currency)}
          detail={savingsDetail}
          tone="ok"
          icon={<SparkIcon />}
        />
        <StatCard
          label="Ahorro verificado"
          value={formatMoney(verified?.total_amount || 0, verified?.currency || currency)}
          detail={`${verified?.count ?? 0} registro(s) con evidencia este mes`}
          tone="brand"
          icon={<CheckIcon />}
        />
        <StatCard
          label="Gasto proyectado"
          value={formatMoney(forecast.projected_spend || 0, currency)}
          detail={forecastDetail}
          tone="brand"
          icon={<CheckIcon />}
        />
      </section>

      <div className="dashboard-grid">
        <section className="card chart-card">
          <div className="card-head">
            <div>
              <h2>Gasto mensual auditado</h2>
              <p>Últimos {months} meses en {currency}.</p>
            </div>
          </div>
          {loading ? (
            <div className="empty-state">Cargando serie mensual…</div>
          ) : monthly.length === 0 ? (
            <div className="empty-state">Sin compras registradas en el período.</div>
          ) : (
            <div className="stack">
              {monthly.map((row) => (
                <div key={row.month} className="stack" style={{ gap: 4 }}>
                  <div className="card-head" style={{ padding: 0 }}>
                    <span className="muted small">{formatMonth(row.month)}</span>
                    <span className="mono small">{formatMoney(row.spend, currency)}</span>
                  </div>
                  <div className="quota-track">
                    <span
                      className="quota-fill ok"
                      style={{ width: `${Math.max(2, (Number(row.spend) / maxSpend) * 100)}%` }}
                    />
                  </div>
                  <span className="muted small">
                    {row.items} ítems · precio promedio {formatMoney(row.avg_price, currency)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="stack">
          <section className="card">
            <div className="card-head">
              <div>
                <h2>Oportunidades</h2>
                <p>Ahorro estimado comparado con el mejor precio.</p>
              </div>
              <button type="button" className="button ghost small" onClick={() => onNavigate?.("opportunities")}>
                Abrir <ArrowRightIcon />
              </button>
            </div>
            <div className="enterprise-metrics">
              <div className="enterprise-metric ok">
                <span>Ahorro potencial</span>
                <strong>{formatMoney(opportunities.total_potential_savings || 0, currency)}</strong>
                <small>{opportunities.opportunities ?? 0} ítem(s) sobrevalorados</small>
              </div>
              <div className="enterprise-metric warning">
                <span>Proveedores afectados</span>
                <strong>{opportunities.suppliers_affected ?? 0}</strong>
                <small>Con oportunidades activas</small>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <div>
                <h2>Aprobación automática</h2>
                <p>Ítems listos para auto-aprobar.</p>
              </div>
              <button type="button" className="button ghost small" onClick={() => onNavigate?.("auto-approvals")}>
                Abrir <ArrowRightIcon />
              </button>
            </div>
            <div className="enterprise-metrics">
              <div className="enterprise-metric">
                <span>Auto-aprobables</span>
                <strong>{approvals.auto_eligible ?? 0}</strong>
                <small>{formatMoney(approvals.auto_amount || 0, currency)}</small>
              </div>
              <div className="enterprise-metric warning">
                <span>Requieren revisión</span>
                <strong>{approvals.needs_review ?? 0}</strong>
                <small>{formatMoney(approvals.review_amount || 0, currency)}</small>
              </div>
            </div>
          </section>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Mayores alzas de precio</h2>
            <p>Últimos 30 días contra los 90 días anteriores.</p>
          </div>
        </div>
        {loading ? (
          <div className="empty-state">Calculando variaciones…</div>
        ) : !analytics?.top_increases?.length ? (
          <div className="empty-state">Sin variaciones relevantes en el período.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Precio reciente</th>
                  <th>Precio base</th>
                  <th>Variación</th>
                  <th>Cantidad</th>
                  <th>Gasto</th>
                </tr>
              </thead>
              <tbody>
                {analytics.top_increases.map((row) => (
                  <tr key={`${row.product_key}-${row.base_unit || ""}`}>
                    <td>
                      <strong>{row.description || row.product_key}</strong>
                      <div className="muted small">{row.base_unit || "unidad"}</div>
                    </td>
                    <td className="mono">{formatMoney(row.recent_price, currency)}</td>
                    <td className="mono">{formatMoney(row.baseline_price, currency)}</td>
                    <td>
                      <span className={`badge ${row.change_pct >= 20 ? "status-rejected" : "priority-high"}`}>
                        {percent(row.change_pct, 1)}
                      </span>
                    </td>
                    <td>{formatNumber(row.quantity, 2)}</td>
                    <td className="mono">{formatMoney(row.spend, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
        </>
      )}
    </div>
  );
}
