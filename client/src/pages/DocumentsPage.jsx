import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import DocumentsTable from "../components/DocumentsTable";
import UploadCard from "../components/UploadCard";

export default function DocumentsPage() {
  const { canOperate } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reprocessingId, setReprocessingId] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await api("/api/documents?page=1&page_size=50");
      setDocuments(data.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar los documentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const hasPending = documents.some((doc) => ["queued", "processing"].includes(doc.status));
    if (!hasPending) return undefined;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [documents, load]);

  async function handleReprocess(document) {
    setReprocessingId(document.id);
    setError("");
    try {
      await api(`/api/documents/${document.id}/reprocess`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message || "No se pudo reencolar el documento.");
    } finally {
      setReprocessingId(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Ingesta documental</div>
          <h2>Documentos de compra</h2>
          <p>Cada archivo se procesa de forma asíncrona y queda asociado a tu organización.</p>
        </div>
        <button type="button" className="button ghost" onClick={load}>
          Actualizar
        </button>
      </section>

      {canOperate ? <UploadCard onUploaded={load} /> : null}

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Historial de documentos</h2>
            <p>{loading ? "Cargando…" : `${documents.length} documentos en esta vista`}</p>
          </div>
        </div>
        {loading ? (
          <div className="empty-state">Cargando documentos…</div>
        ) : (
          <DocumentsTable
            documents={documents}
            onReprocess={canOperate ? handleReprocess : undefined}
            reprocessingId={reprocessingId}
          />
        )}
      </section>
    </div>
  );
}
