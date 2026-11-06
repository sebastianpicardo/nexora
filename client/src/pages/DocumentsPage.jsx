import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import DocumentsTable from "../components/DocumentsTable";
import DocumentDetailModal from "../components/DocumentDetailModal";
import InfoHint from "../components/InfoHint";
import UploadCard from "../components/UploadCard";
import { ArrowLeftIcon, ArrowRightIcon } from "../components/Icons";

function processedFilename(document, format) {
  const name = document.original_filename || `documento-${document.id}`;
  const stem = name.replace(/\.[^.]+$/, "") || "documento";
  return `${stem}-procesado.${format}`;
}

export default function DocumentsPage() {
  const { canOperate } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reprocessingId, setReprocessingId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);
  const [exporting, setExporting] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      const data = await api(`/api/documents?${params.toString()}`);
      setDocuments(data.items || []);
      setTotal(data.total || 0);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar los documentos.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

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

  async function handleDownload(document) {
    setDownloadingId(document.id);
    setError("");
    try {
      await downloadFile(
        `/api/documents/${document.id}/file`,
        document.original_filename || `documento-${document.id}`,
      );
    } catch (err) {
      setError(err.message || "No se pudo descargar el documento original.");
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleExport(document, format) {
    setExporting(`${document.id}:${format}`);
    setError("");
    try {
      await downloadFile(
        `/api/documents/${document.id}/export?format=${format}`,
        processedFilename(document, format),
      );
    } catch (err) {
      setError(err.message || "No se pudo exportar el documento procesado.");
    } finally {
      setExporting("");
    }
  }

  function handleUploaded() {
    if (page !== 1) {
      setPage(1);
      return;
    }
    load();
  }

  function changePageSize(value) {
    setPageSize(Number(value));
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Ingesta documental</div>
          <h2 className="title-with-help">
            Documentos de compra
            <InfoHint title="¿Qué es esta pantalla?">
              Centraliza cotizaciones, facturas y listas de precios. Cada archivo se procesa de forma
              asíncrona para extraer proveedor, ítems, unidades y precios auditables.
            </InfoHint>
          </h2>
          <p>Cada archivo se procesa de forma asíncrona y queda asociado a tu organización.</p>
        </div>
        <button type="button" className="button ghost" onClick={load}>
          Actualizar
        </button>
      </section>

      {canOperate ? <UploadCard onUploaded={handleUploaded} /> : null}

      {error ? <div className="alert error">{error}</div> : null}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Historial de documentos</h2>
            <p>
              {loading
                ? "Cargando…"
                : `${documents.length} de ${total} documentos · página ${page} de ${totalPages}`}
            </p>
          </div>
          <label className="page-size">
            <span>Por página</span>
            <select value={pageSize} onChange={(event) => changePageSize(event.target.value)}>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </label>
        </div>
        {loading ? (
          <div className="empty-state">Cargando documentos…</div>
        ) : (
          <>
            <DocumentsTable
              documents={documents}
              onReprocess={canOperate ? handleReprocess : undefined}
              reprocessingId={reprocessingId || undefined}
              onView={setSelected}
              onDownload={downloadingId ? undefined : handleDownload}
              onExport={exporting ? undefined : handleExport}
            />
            <div className="pagination">
              <button
                type="button"
                className="button ghost small"
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                <ArrowLeftIcon /> Anterior
              </button>
              <span>
                Página {page} de {totalPages}
              </span>
              <button
                type="button"
                className="button ghost small"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                Siguiente <ArrowRightIcon />
              </button>
            </div>
          </>
        )}
      </section>

      {selected ? (
        <DocumentDetailModal
          key={selected.id}
          document={selected}
          onClose={() => setSelected(null)}
          onDownload={handleDownload}
          onExport={handleExport}
          onReprocess={canOperate ? handleReprocess : undefined}
          reprocessing={reprocessingId === selected.id}
        />
      ) : null}
    </div>
  );
}
