import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { SparkIcon } from "./Icons";

export default function DemoDataBanner({
  title = "Aún no hay datos para mostrar",
  description = "Sube una factura o carga el ejemplo de ferretería de 90 días para ver esta vista funcionando desde el primer minuto.",
  onLoaded,
  compact = false,
}) {
  const { canManage } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadDemo() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const result = await api("/api/enterprise/onboarding/demo?months=3", { method: "POST" });
      await onLoaded?.();
      setSuccess(
        result?.already_seeded
          ? "Los datos de ejemplo ya estaban cargados."
          : "Ejemplo de ferretería cargado. La información ya está disponible."
      );
    } catch (err) {
      setError(err.message || "No se pudieron cargar los datos demo.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={`demo-data-banner${compact ? " compact" : ""}`}>
      <div className="demo-data-icon">
        <SparkIcon />
      </div>
      <div className="demo-data-copy">
        <strong>{title}</strong>
        <p>{description}</p>
        {!canManage ? (
          <span className="muted small">
            Pide a un administrador que cargue los datos de prueba.
          </span>
        ) : null}
        {success ? <span className="demo-data-success">{success}</span> : null}
        {error ? <span className="demo-data-error">{error}</span> : null}
      </div>
      {canManage ? (
        <button type="button" className="button primary" disabled={pending} onClick={loadDemo}>
          {pending ? "Cargando ejemplo..." : "Cargar ejemplo (90 días)"}
        </button>
      ) : null}
    </section>
  );
}
