import { useState } from "react";
import { api } from "../lib/api";

export default function WelcomeBanner({ canOperate = false, onNavigate }) {
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState("");

  const loadDemo = async () => {
    setSeeding(true);
    setError("");
    try {
      await api("/api/enterprise/onboarding/demo", { method: "POST" });
      window.location.reload();
    } catch (err) {
      setError(err.message || "No se pudo cargar la demo.");
      setSeeding(false);
    }
  };

  return (
    <section className="welcome-banner">
      <div>
        <span className="eyebrow">Bienvenido</span>
        <h2>Empieza a auditar tus compras</h2>
        <p className="muted">
          Sube tu primer documento o carga 12 meses de historial demo para ver ahorro real,
          pronósticos y excepciones desde el primer minuto.
        </p>
        {error ? <div className="alert error">{error}</div> : null}
      </div>
      <div className="welcome-banner-actions">
        {canOperate ? (
          <button type="button" className="button primary" disabled={seeding} onClick={loadDemo}>
            {seeding ? "Cargando demo..." : "Cargar demo de 12 meses"}
          </button>
        ) : null}
        <button type="button" className="primary-button" onClick={() => onNavigate?.("documents")}>
          Subir documento
        </button>
      </div>
    </section>
  );
}
