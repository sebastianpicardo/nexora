import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { CheckIcon, UploadIcon } from "./Icons";

export default function SiiCompletenessCard({ onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/api/leaks/rcv/completeness")
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return null;
  const total = Number(data?.total_documents || 0);
  const complete = total > 0 && Number(data?.missing || 0) === 0;
  const tone = complete ? "ok" : total ? "warning" : "empty";

  return (
    <section className={`card sii-status-card ${tone}`}>
      <div className="sii-status-icon">{complete ? <CheckIcon /> : <UploadIcon />}</div>
      <div>
        <strong>Completitud SII</strong>
        <p>
          {data
            ? data.message
            : "Revisando el Registro de Compras del período…"}
        </p>
      </div>
      {!complete ? (
        <button type="button" className="button ghost small" onClick={() => onNavigate?.("audit-express")}>
          Importar RCV
        </button>
      ) : (
        <span className="badge status-processed">Completo</span>
      )}
    </section>
  );
}
