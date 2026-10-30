import { formatDateTime, labelize } from "../lib/format";

export default function ExceptionsTable({ exceptions, onResolve, compact = false }) {
  if (!exceptions?.length) {
    return (
      <div className="empty-state">
        <div className="empty-title">Sin excepciones pendientes</div>
        <p>Los documentos procesados sin alertas aparecen como auto-aprobados.</p>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Severidad</th>
            <th>Tipo</th>
            <th>Ítem</th>
            {!compact ? <th>Documento</th> : null}
            <th>Motivo</th>
            <th>Fecha</th>
            {onResolve ? <th className="right">Acción</th> : null}
          </tr>
        </thead>
        <tbody>
          {exceptions.map((exception) => (
            <tr key={exception.id}>
              <td>
                <span className={`badge severity-${exception.severity}`}>
                  {labelize(exception.severity)}
                </span>
              </td>
              <td>{labelize(exception.type)}</td>
              <td>
                <div className="cell-title">
                  {exception.item_description || exception.supplier_name || "Documento completo"}
                </div>
                {exception.item_sku ? <div className="cell-sub">SKU {exception.item_sku}</div> : null}
              </td>
              {!compact ? (
                <td>
                  <div className="cell-title">{exception.document_filename}</div>
                  <div className="cell-sub">{exception.supplier_name || "Sin proveedor"}</div>
                </td>
              ) : null}
              <td className="reason-cell">{exception.reason}</td>
              <td>{formatDateTime(exception.created_at)}</td>
              {onResolve ? (
                <td className="right">
                  <button
                    type="button"
                    className="button ghost small"
                    onClick={() => onResolve(exception)}
                  >
                    Resolver
                  </button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
