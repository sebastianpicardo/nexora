import { formatDateTime, labelize } from "../lib/format";
import { DownloadIcon, SearchIcon, CheckIcon, DocumentsIcon } from "./Icons";

export default function DocumentsTable({
  documents,
  onReprocess,
  reprocessingId,
  onView,
  onDownload,
  onExport,
  onIntegrationAction,
  compact = false,
}) {
  if (!documents?.length) {
    return (
      <div className="empty-state">
        <div className="empty-title">Todavía no hay documentos</div>
        <p>Sube tu primera cotización o factura para comenzar la auditoría.</p>
      </div>
    );
  }

  const showActions = Boolean(onView || onDownload || onExport || onReprocess) && !compact;

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Archivo</th>
            <th>Proveedor</th>
            {!compact ? <th>Tipo</th> : null}
            <th>Fecha</th>
            <th>Estado</th>
            {showActions ? <th className="right">Acciones</th> : null}
            {onIntegrationAction ? <th className="right">Integraciones</th> : null}
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>
                {onView ? (
                  <button
                    type="button"
                    className="cell-link"
                    onClick={() => onView(document)}
                    title="Ver detalle del documento"
                  >
                    {document.original_filename}
                  </button>
                ) : (
                  <div className="cell-title">{document.original_filename}</div>
                )}
                {document.error_message ? (
                  <div className="cell-error">{document.error_message}</div>
                ) : null}
              </td>
              <td>{document.supplier_name || "Sin asignar"}</td>
              {!compact ? <td>{labelize(document.doc_type)}</td> : null}
              <td>{formatDateTime(document.created_at)}</td>
              <td>
                <span className={`badge status-${document.status}`}>{labelize(document.status)}</span>
              </td>
                  {showActions ? (
                    <td className="right">
                      <div className="table-actions">
                        {onView ? (
                          <button
                            type="button"
                            className="button ghost small"
                            onClick={() => onView(document)}
                            title="Ver metadatos, descargar o reprocesar"
                          >
                            Detalle
                          </button>
                        ) : null}
                        {onDownload ? (
                          <button
                            type="button"
                            className="button ghost icon-only"
                            onClick={() => onDownload(document)}
                            title="Descargar original"
                          >
                            <DownloadIcon />
                          </button>
                        ) : null}
                        {onExport ? (
                          <>
                            <button
                              type="button"
                              className="button ghost small"
                              onClick={() => onExport(document, "xlsx")}
                              title="Exportar procesado a Excel"
                            >
                              XLSX
                            </button>
                            <button
                              type="button"
                              className="button ghost small"
                              onClick={() => onExport(document, "pdf")}
                              title="Exportar procesado a PDF"
                            >
                              PDF
                            </button>
                          </>
                        ) : null}
                        {onReprocess &&
                        (document.status === "failed" || document.status === "processed") ? (
                          <button
                            type="button"
                            className="button ghost small"
                            onClick={() => onReprocess(document)}
                            disabled={reprocessingId === document.id}
                          >
                            {reprocessingId === document.id ? "Enviando…" : "Reprocesar"}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  ) : null}
                  {onIntegrationAction ? (
                    <td className="right">
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => onIntegrationAction(document, "chilecompra", "search_items")}
                          title="Buscar precio en ChileCompra"
                        >
                          <SearchIcon />
                        </button>
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => onIntegrationAction(document, "sii", "validate_rut")}
                          title="Validar RUT en SII"
                        >
                          <CheckIcon />
                        </button>
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => onIntegrationAction(document, "google_workspace", "save_drive")}
                          title="Guardar en Google Drive"
                        >
                          <DocumentsIcon />
                        </button>
                      </div>
                    </td>
                  ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
