import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney, formatNumber, labelize } from "../lib/format";
import DocumentsTable from "../components/DocumentsTable";
import ExceptionsTable from "../components/ExceptionsTable";
import QuotaCard from "../components/QuotaCard";
import SpendChart from "../components/SpendChart";
import StatCard from "../components/StatCard";
import UploadCard from "../components/UploadCard";
import AppBanner from "../components/AppBanner";
import ActionEmptyState from "../components/ActionEmptyState";
import QuickGuide from "../components/QuickGuide";
import NextStepCard from "../components/NextStepCard";
import { DocumentsIcon, ExceptionsIcon, PricesIcon, SparkIcon, SuppliersIcon, CheckIcon } from "../components/Icons";

export default function DashboardPage({ onNavigate, onUpload }) {
  const { organization, billing, canOperate } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [autoPaused, setAutoPaused] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [currency, setCurrency] = useState("");

  useEffect(() => {
    if (!currency && organization?.default_currency) {
      setCurrency(organization.default_currency);
    }
  }, [organization?.default_currency, currency]);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    let failures = 0;

    async function poll() {
      try {
        const query = currency ? `?currency=${encodeURIComponent(currency)}` : "";
        const data = await api(`/api/dashboard/summary${query}`);
        if (cancelled) return;
        failures = 0;
        setSummary(data);
        setError("");
        setAutoPaused(false);
        timer = setTimeout(poll, 8000);
      } catch (err) {
        if (cancelled) return;
        failures += 1;
        setError(err.message || "No se pudo cargar el resumen.");
        if (failures >= 3) {
          setAutoPaused(true);
        } else {
          timer = setTimeout(poll, Math.min(8000 * 2 ** failures, 30000));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [refreshKey, currency]);

  function retry() {
    setLoading(true);
    setError("");
    setAutoPaused(false);
    setRefreshKey((key) => key + 1);
  }

  const spendByCurrency = summary?.spend_by_currency || [];
  const activeCurrency = currency || organization?.default_currency || "CLP";
  const primarySpend = spendByCurrency.find((row) => row.currency === activeCurrency);
  const currencyOptions = Array.from(
    new Set([
      activeCurrency,
      organization?.default_currency,
      ...spendByCurrency.map((row) => row.currency),
    ].filter(Boolean)),
  );
  const quota = summary?.quota || billing?.usage;
  const planName = billing?.subscription?.plan_name || "Free";
  const hasActivity = Boolean(
    summary &&
      (summary.documents_total > 0 ||
        summary.items_total > 0 ||
        summary.exceptions_pending > 0 ||
        summary.documents_pending > 0 ||
        spendByCurrency.length > 0),
  );
  const showEmpty = !loading && summary && !hasActivity;
  const showLoadError = !loading && !summary && Boolean(error);

  // KPIs principales calculados
  const totalSpend = Number(primarySpend?.amount || 0);
  const totalSavings = Number(summary?.total_savings || 0);
  const savingsRate = totalSpend > 0 ? Math.round((totalSavings / totalSpend) * 100) : 0;
  const spendSeries = (summary?.monthly_purchases || []).map((row) => Number(row.spend || 0));
  const metricsAreZero =
    Boolean(summary) &&
    !showEmpty &&
    totalSpend <= 0 &&
    totalSavings <= 0 &&
    Number(summary?.exceptions_pending || 0) === 0 &&
    Number(summary?.approvals_pending || 0) === 0 &&
    (Number(summary?.documents_pending || 0) > 0 || Number(summary?.suppliers_count || 0) === 0);

  return (
    <div className="page-stack">
      <AppBanner onNavigate={onNavigate} onUpload={canOperate ? onUpload : undefined} />
      <QuickGuide activeStep={1} />

      {error && summary ? (
        <div className="alert error">
          {autoPaused
            ? "La actualización automática se pausó después de varios intentos fallidos. Revisa tu conexión y vuelve a intentarlo."
            : error}
        </div>
      ) : null}

      {loading && !summary ? (
        <section className="card dashboard-empty">
          <div className="empty-orb"><SparkIcon /></div>
          <h2>Cargando dashboard</h2>
          <p>Estamos reuniendo tus documentos, precios y excepciones.</p>
        </section>
      ) : null}

      {showLoadError ? (
        <section className="card dashboard-empty">
          <div className="empty-orb"><SparkIcon /></div>
          <h2>No pudimos cargar el dashboard</h2>
          <p>
            {autoPaused
              ? "La actualización automática se pausó para no repetir solicitudes fallidas."
              : error}
          </p>
          <div className="empty-actions">
            <button type="button" className="button primary" onClick={retry}>
              Reintentar
            </button>
          </div>
        </section>
      ) : null}

      {showEmpty ? (
        <ActionEmptyState
          icon={<SparkIcon />}
          title="Sin registros aún"
          description="Sube tu primera cotización o factura para ver compras, precios normalizados y excepciones. También puedes explorar NEXORA con datos de demostración."
          onUpload={canOperate ? onUpload : undefined}
          onLoaded={retry}
        />
      ) : null}

      {summary && !showEmpty ? (
        <>
          {metricsAreZero ? (
            <NextStepCard
              summary={summary}
              canOperate={canOperate}
              onUpload={onUpload}
              onNavigate={onNavigate}
              onRefresh={retry}
            />
          ) : null}

          {/* KPIs principales */}
          {!metricsAreZero ? (
            <section className="stats-grid">
              <StatCard
                label="Compra del mes"
                value={formatMoney(totalSpend, activeCurrency)}
                detail={`${summary?.documents_total ?? 0} documentos · ${summary?.items_total ?? 0} ítems`}
                icon={<DocumentsIcon />}
                sparkline={spendSeries}
              />
              <StatCard
                label="Ahorro estimado"
                value={formatMoney(totalSavings, activeCurrency)}
                detail={`${savingsRate}% de la compra auditada`}
                tone="ok"
                icon={<SparkIcon />}
                trend={savingsRate}
                trendHint="vs. gasto"
              />
              <StatCard
                label="Excepciones pendientes"
                value={loading ? "—" : summary?.exceptions_pending ?? 0}
                detail={`${summary?.price_alerts_pending ?? 0} alertas de alza de precio`}
                tone="warning"
                icon={<ExceptionsIcon />}
              />
              <StatCard
                label="Aprobaciones pendientes"
                value={loading ? "—" : summary?.approvals_pending ?? 0}
                detail={formatMoney(Number(summary?.approvals_amount || 0), activeCurrency)}
                tone="brand"
                icon={<CheckIcon />}
              />
              <StatCard
                label="Proveedores activos"
                value={loading ? "—" : summary?.suppliers_count ?? 0}
                detail={`${summary?.scorecards_count ?? 0} con score calculado`}
                icon={<SuppliersIcon />}
              />
            </section>
          ) : null}

          <div className="dashboard-grid">
            <section className="card chart-card">
              <div className="card-head">
                <div>
                  <h2>Compras y alertas mensuales</h2>
                  <p>Últimos 6 meses en {activeCurrency}.</p>
                </div>
                <div className="card-head-tools">
                  <label className="page-size">
                    <span>Moneda</span>
                    <select
                      value={activeCurrency}
                      onChange={(event) => setCurrency(event.target.value)}
                    >
                      {currencyOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
              <SpendChart data={summary?.monthly_purchases || []} currency={activeCurrency} />
            </section>

            <section className="stack">
              <QuotaCard quota={quota} planName={planName} />
              <div className="quick-actions">
                <button type="button" className="quick-action" onClick={() => onNavigate("audit-express")}>
                  <span className="quick-icon"><SparkIcon /></span>
                  <span>
                    <strong>Auditoría Express</strong>
                    <small>Fugas, sobrecostos y márgenes</small>
                  </span>
                </button>
                {canOperate ? (
                  <button type="button" className="quick-action" onClick={onUpload}>
                    <span className="quick-icon"><DocumentsIcon /></span>
                    <span>
                      <strong>Subir documento</strong>
                      <small>Cotización, factura o lista de precios</small>
                    </span>
                  </button>
                ) : null}
                <button type="button" className="quick-action" onClick={() => onNavigate("items")}>
                  <span className="quick-icon"><PricesIcon /></span>
                  <span>
                    <strong>Precios auditados</strong>
                    <small>Explora el histórico normalizado</small>
                  </span>
                </button>
                <button type="button" className="quick-action" onClick={() => onNavigate("exceptions")}>
                  <span className="quick-icon"><ExceptionsIcon /></span>
                  <span>
                    <strong>Bandeja HITL</strong>
                    <small>Resuelve alertas con evidencia</small>
                  </span>
                </button>
                <button type="button" className="quick-action" onClick={() => onNavigate("approvals")}>
                  <span className="quick-icon"><CheckIcon /></span>
                  <span>
                    <strong>Aprobaciones</strong>
                    <small>Compra pendiente de decidir</small>
                  </span>
                </button>
              </div>
            </section>
          </div>

          <div className="two-column">
            <section className="stack">
              {canOperate ? <UploadCard onUploaded={retry} /> : null}
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Documentos recientes</h2>
                    <p>Últimas cotizaciones, facturas y listas cargadas.</p>
                  </div>
                  <button type="button" className="button ghost small" onClick={() => onNavigate("documents")}>
                    Ver todos
                  </button>
                </div>
                <DocumentsTable documents={summary?.recent_documents || []} compact />
              </section>
            </section>

            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Requiere tu revisión</h2>
                  <p>Ítems con baja confianza o variaciones relevantes.</p>
                </div>
                <button type="button" className="button ghost small" onClick={() => onNavigate("exceptions")}>
                  Abrir bandeja
                </button>
              </div>
              <ExceptionsTable
                exceptions={summary?.pending_exceptions || []}
                onResolve={canOperate ? () => onNavigate("exceptions") : undefined}
                compact
              />
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
