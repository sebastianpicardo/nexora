import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { CheckIcon, DocumentsIcon, ExceptionsIcon, SparkIcon } from "./Icons";

export default function NextStepCard({ summary, canOperate, onUpload, onNavigate, onRefresh }) {
  const [demoSeeded, setDemoSeeded] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/enterprise/onboarding")
      .then((data) => {
        if (!cancelled) setDemoSeeded(Boolean(data?.demo_seeded));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function seedDemo() {
    setPending(true);
    setError("");
    try {
      await api("/api/enterprise/onboarding/demo?months=3", { method: "POST", body: "{}" });
      setDemoSeeded(true);
      onRefresh?.();
    } catch (err) {
      setError(err.message || "No se pudo cargar la demo.");
    } finally {
      setPending(false);
    }
  }

  const documentsPending = Number(summary?.documents_pending || 0);
  const exceptionsPending = Number(summary?.exceptions_pending || 0);
  const approvalsPending = Number(summary?.approvals_pending || 0);

  let icon = <SparkIcon />;
  let title = "Tu siguiente paso";
  let description = "Sube una cotización, factura o lista de precios y NEXORA la procesará automáticamente.";
  let action = canOperate ? (
    <button type="button" className="button primary" onClick={onUpload}>
      <DocumentsIcon /> Subir documento
    </button>
  ) : null;

  if (documentsPending > 0) {
    icon = <DocumentsIcon />;
    title = `Procesando ${documentsPending} documento${documentsPending === 1 ? "" : "s"}`;
    description = "Los precios y excepciones aparecerán aquí en cuanto termine el procesamiento automático.";
    action = (
      <button type="button" className="button primary" onClick={() => onNavigate("documents")}>
        Ver documentos
      </button>
    );
  } else if (exceptionsPending > 0) {
    icon = <ExceptionsIcon />;
    title = `Tienes ${exceptionsPending} excepción${exceptionsPending === 1 ? "" : "es"} por revisar`;
    description = "Resuelve las alertas con la evidencia disponible para mantener tus precios bajo control.";
    action = (
      <button type="button" className="button primary" onClick={() => onNavigate("exceptions")}>
        Abrir bandeja
      </button>
    );
  } else if (approvalsPending > 0) {
    icon = <CheckIcon />;
    title = `Tienes ${approvalsPending} aprobación${approvalsPending === 1 ? "" : "es"} pendiente${approvalsPending === 1 ? "" : "s"}`;
    description = "Decide en un clic qué compras continúan y cuáles se detienen.";
    action = (
      <button type="button" className="button primary" onClick={() => onNavigate("approvals")}>
        Revisar aprobaciones
      </button>
    );
  }

  return (
    <section className="card next-step-card">
      <div className="next-step-icon">{icon}</div>
      <div className="next-step-body">
        <span className="next-step-eyebrow">Qué hacer hoy</span>
        <h2>{title}</h2>
        <p>{description}</p>
        {error ? <div className="alert error">{error}</div> : null}
      </div>
      <div className="next-step-actions">
        {action}
        {canOperate ? (
          <button
            type="button"
            className="button ghost"
            onClick={demoSeeded ? () => onNavigate("enterprise") : seedDemo}
            disabled={pending}
          >
            <SparkIcon /> {demoSeeded ? "Gestionar datos demo" : "Cargar ejemplo de ferretería (90 días)"}
          </button>
        ) : null}
      </div>
    </section>
  );
}
