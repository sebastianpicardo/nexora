import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { SparkIcon, UploadIcon } from "./Icons";

export default function ActionEmptyState({
  icon,
  title,
  description,
  onUpload,
  onLoaded,
  uploadLabel = "Subir primera factura",
  demoLabel = "Cargar datos de demostración",
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
      const result = await api("/api/enterprise/onboarding/demo", { method: "POST" });
      await onLoaded?.();
      setSuccess(
        result?.already_seeded
          ? "Los datos demo ya estaban cargados."
          : "Datos demo cargados correctamente."
      );
    } catch (err) {
      setError(err.message || "No se pudieron cargar los datos demo.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="empty-state-card action-empty-state">
      <div className="empty-state-icon">{icon || <SparkIcon />}</div>
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="empty-state-actions">
        {onUpload ? (
          <button type="button" className="button primary" onClick={onUpload}>
            <UploadIcon /> {uploadLabel}
          </button>
        ) : null}
        {canManage ? (
          <button
            type="button"
            className="button ghost"
            disabled={pending}
            onClick={loadDemo}
          >
            <SparkIcon /> {pending ? "Cargando demo…" : demoLabel}
          </button>
        ) : null}
      </div>
      {!canManage ? (
        <p className="muted small">
          Pide a un administrador que cargue los datos de demostración.
        </p>
      ) : null}
      {success ? <p className="demo-data-success">{success}</p> : null}
      {error ? <p className="demo-data-error">{error}</p> : null}
    </section>
  );
}
