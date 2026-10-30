import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import DocumentsTable from "../components/DocumentsTable";
import ExceptionsTable from "../components/ExceptionsTable";
import QuotaCard from "../components/QuotaCard";
import SpendChart from "../components/SpendChart";
import StatCard from "../components/StatCard";
import UploadCard from "../components/UploadCard";
import { DocumentsIcon, ExceptionsIcon, PricesIcon, SparkIcon } from "../components/Icons";
import WelcomeBanner from "../components/WelcomeBanner";

export default function DashboardPage({ onNavigate }) {
  const { organization, billing, canOperate } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [autoPaused, setAutoPaused] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    let failures = 0;

    async function poll() {
      try {
        const data = await api("/api/dashboard/summary");
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
  }, [refreshKey]);

  function retry() {
    setLoading(true);
    setError("");
    setAutoPaused(false);
    setRefreshKey((key) => key + 1);
  }

  const spendByCurrency = summary?.spend_by_currency || [];
  const primarySpend = spendByCurrency[0];
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

  return (
    <div className="page-stack">
      {!summary || !hasActivity ? (
        <WelcomeBanner />
      ) : null}

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
        <section className="card dashboard-empty">
          <div className="empty-orb"><SparkIcon /></div>
          <h2>Sin registros aún</h2>
          <p>
            Sube tu primera cotización o factura para comenzar a ver compras, precios
            normalizados y excepciones en este panel.
          </p>
          <div className="empty-actions">
            {canOperate ? (
              <button type="button" className="button primary" onClick={() => onNavigate("documents")}>
                Cargar documento
              </button>
            ) : null}
            <button type="button" className="button ghost" onClick={retry}>
              Actualizar
            </button>
          </div>
        </section>
      ) : null}

      {summary && !showEmpty ? (
        <>
      <section className="stats-grid">
        <StatCard
          label="Documentos"
          value={loading ? "—" : summary?.documents_total ?? 0}
          detail={`${summary?.documents_processed ?? 0} procesados · ${
            summary?.documents_pending ?? 0
          } en curso`}
          icon={<DocumentsIcon />}
        />
        <StatCard
          label="Excepciones pendientes"
          value={loading ? "—" : summary?.exceptions_pending ?? 0}
          detail={`${summary?.price_alerts_pending ?? 0} alertas de alza`}
          tone="warning"
          icon={<ExceptionsIcon />}
        />
        <StatCard
          label="Ítems auditados"
          value={loading ? "—" : summary?.items_total ?? 0}
          detail="Histórico normalizado"
          tone="brand"
          icon={<PricesIcon />}
        />
        <StatCard
          label="Compra del mes"
          value={loading ? "—" : primarySpend ? formatMoney(primarySpend.amount, primarySpend.currency) : "—"}
          detail={
            spendByCurrency.length > 1
              ? `${spendByCurrency.length} monedas con compras este mes`
              : primarySpend
                ? `Moneda ${primarySpend.currency}`
                : "Sin compras registradas este mes"
          }
        />
      </section>

      <div className="dashboard-grid">
        <section className="card chart-card">
          <div className="card-head">
            <div>
              <h2>Compras y alertas</h2>
              <p>Últimos 6 meses en {organization?.default_currency || "CLP"}.</p>
            </div>
            <span className="soft-chip">Tendencia</span>
          </div>
          <SpendChart data={summary?.monthly_purchases || []} currency={organization?.default_currency} />
        </section>

        <section className="stack">
          <QuotaCard quota={quota} planName={planName} />
          <div className="quick-actions">
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
