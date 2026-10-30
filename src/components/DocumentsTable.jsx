import { formatDateTime, labelize } from "../lib/format";

export default function DocumentsTable({ documents, onReprocess, reprocessingId, compact = false }) {
  if (!documents?.length) {
    return (
      <div className="empty-state">
        <div className="empty-title">Todavía no hay documentos</div>
        <p>Sube tu primera cotización o factura para comenzar la auditoría.</p>
      </div>
    );
  }

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
            {onReprocess ? <th className="right">Acción</th> : null}
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>
                <div className="cell-title">{document.original_filename}</div>
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
              {onReprocess ? (
                <td className="right">
                  {document.status === "failed" || document.status === "processed" ? (
                    <button
                      type="button"
                      className="button ghost small"
                      onClick={() => onReprocess(document)}
                      disabled={reprocessingId === document.id}
                    >
                      {reprocessingId === document.id ? "Enviando…" : "Reprocesar"}
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
