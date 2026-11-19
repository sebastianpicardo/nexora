import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { SparkIcon } from "./Icons";

export default function LeakAuditCard({ onNavigate, summary: summaryProp = null }) {
  const [audit, setAudit] = useState(null);
  const [dashboardSummary, setDashboardSummary] = useState(summaryProp);
  const [error, setError] = useState("");

  useEffect(() => {
    if (summaryProp) setDashboardSummary(summaryProp);
  }, [summaryProp]);

  useEffect(() => {
    if (summaryProp) return;
    let cancelled = false;
    api("/api/dashboard/summary")
      .then((result) => {
        if (!cancelled) setDashboardSummary(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [summaryProp]);

  useEffect(() => {
    let cancelled = false;
    api("/api/leaks/audit?days=90")
      .then((result) => {
        if (!cancelled) setAudit(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error && !dashboardSummary) return null;

  const auditSummary = audit?.summary || {};
  const dashboard = dashboardSummary || {};
  const potential = Number(auditSummary.potential_savings || 0);
  const findings = Number(auditSummary.findings_total || 0);
  const exceptionsPending = Number(dashboard.exceptions_pending || 0);
  const priceAlerts = Number(dashboard.price_alerts_pending || 0);
  const documentsTotal = Number(dashboard.documents_total || 0);
  const currency = audit?.currency || dashboard?.savings_currency || "CLP";

  let message = "Calculando sobrecostos y márgenes en riesgo…";
  let actionLabel = "Ver diagnóstico";
  let action = "audit-express";

  if (audit) {
    if (potential > 0) {
      message = `Detectamos ${formatMoney(potential, currency)} de ahorro potencial en ${findings} hallazgos.`;
    } else if (exceptionsPending > 0 || priceAlerts > 0) {
      message = `Hay ${exceptionsPending} excepción(es) pendiente(s), incluidas ${priceAlerts} alertas de alza de precio, por revisar.`;
      actionLabel = "Revisar excepciones";
      action = "exceptions";
    } else if (documentsTotal > 0) {
      message = "Sin fugas detectadas en lo auditado. Sigue cargando facturas y listas para ampliar la comparación.";
    } else {
      message = "Carga documentos o el ejemplo de 90 días para calcular sobrecostos y márgenes.";
    }
  }

  return (
    <section className="card leak-audit-card">
      <div className="sii-status-icon">
        <SparkIcon />
      </div>
      <div>
        <strong>Diagnóstico de fugas · 90 días</strong>
        <p>{message}</p>
      </div>
      <button type="button" className="button primary small" onClick={() => onNavigate?.(action)}>
        {actionLabel}
      </button>
    </section>
  );
}
