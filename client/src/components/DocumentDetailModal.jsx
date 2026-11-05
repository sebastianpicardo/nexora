import { useEffect } from "react";
import { formatDateTime, labelize } from "../lib/format";
import { CloseIcon, DownloadIcon, DocumentsIcon } from "./Icons";

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentDetailModal({
  document,
  onClose,
  onDownload,
  onExport,
  onReprocess,
  reprocessing = false,
}) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  if (!document) return null;

  const canExport = document.status === "processed";
  const canReprocess = document.status === "failed" || document.status === "processed";

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className="modal document-detail-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="document-detail-title"
      >
        <div className="modal-head">
          <div>
            <div className="eyebrow"><DocumentsIcon /> Documento</div>
            <h2 id="document-detail-title">{document.original_filename}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} title="Cerrar">
            <CloseIcon />
          </button>
        </div>

        <div className="modal-body">
          <div className="detail-grid">
            <div className="detail-row">
              <span className="detail-label">Proveedor</span>
              <span className="detail-value">{document.supplier_name || "Sin asignar"}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Tipo</span>
              <span className="detail-value">{labelize(document.doc_type)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Estado</span>
              <span className="detail-value">
                <span className={`badge status-${document.status}`}>{labelize(document.status)}</span>
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Tamaño</span>
              <span className="detail-value">{formatBytes(document.file_size_bytes)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Subido</span>
              <span className="detail-value">{formatDateTime(document.created_at)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Procesado</span>
              <span className="detail-value">
                {document.processed_at ? formatDateTime(document.processed_at) : "—"}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Proveedor de extracción</span>
              <span className="detail-value">
                {document.extraction_provider
                  ? `${document.extraction_provider}${document.extraction_model ? ` · ${document.extraction_model}` : ""}`
                  : "—"}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Subido por</span>
              <span className="detail-value">{document.uploaded_by_name || "—"}</span>
            </div>
          </div>

          {document.error_message ? (
            <div className="alert error detail-alert">{document.error_message}</div>
          ) : null}

          {!canExport ? (
            <p className="muted detail-note">
              El documento debe estar procesado para exportar los ítems extraídos.
            </p>
          ) : null}
        </div>

        <div className="modal-actions detail-actions">
          {onReprocess && canReprocess ? (
            <button
              type="button"
              className="button ghost"
              onClick={() => onReprocess(document)}
              disabled={reprocessing}
            >
              {reprocessing ? "Enviando…" : "Reprocesar"}
            </button>
          ) : null}
          <button
            type="button"
            className="button ghost"
            onClick={() => onDownload?.(document)}
          >
            <DownloadIcon /> Original
          </button>
          <button
            type="button"
            className="button ghost"
            onClick={() => onExport?.(document, "pdf")}
            disabled={!canExport}
          >
            Exportar PDF
          </button>
          <button
            type="button"
            className="button primary"
            onClick={() => onExport?.(document, "xlsx")}
            disabled={!canExport}
          >
            <DownloadIcon /> Exportar Excel
          </button>
        </div>
      </div>
    </div>
  );
}
