import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { SparkIcon } from "./Icons";

export default function LeakAuditCard({ onNavigate }) {
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState("");

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

  if (error) return null;
  const summary = audit?.summary || {};
  const potential = Number(summary.potential_savings || 0);
  const findings = Number(summary.findings_total || 0);

  return (
    <section className="card leak-audit-card">
      <div className="sii-status-icon">
        <SparkIcon />
      </div>
      <div>
        <strong>Diagnóstico de fugas · 90 días</strong>
        <p>
          {audit
            ? potential > 0
              ? `Detectamos ${formatMoney(potential, audit.currency)} de ahorro potencial en ${findings} hallazgos.`
              : "Sin fugas detectadas con los datos actuales. Sigue cargando facturas y listas."
            : "Calculando sobrecostos y márgenes en riesgo…"}
        </p>
      </div>
      <button type="button" className="button primary small" onClick={() => onNavigate?.("audit-express")}>
        Ver diagnóstico
      </button>
    </section>
  );
}
