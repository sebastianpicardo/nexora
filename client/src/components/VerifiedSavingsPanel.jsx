import { useCallback, useEffect, useState } from "react";
import { api, downloadFile } from "../lib/api";
import { formatDate, formatMoney } from "../lib/format";
import { CheckIcon, DownloadIcon } from "./Icons";

export default function VerifiedSavingsPanel() {
  const [month, setMonth] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = month ? `?month=${encodeURIComponent(month)}` : "";
      setData(await api(`/api/insights/savings/verified${query}`));
    } catch (err) {
      setError(err.message || "No se pudo cargar el ahorro verificado.");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    load();
  }, [load]);

  const items = data?.items || [];
  const query = month ? `?month=${encodeURIComponent(month)}` : "";

  return (
    <section className="card verified-savings">
      <div className="card-head">
        <div>
          <h2>Registro de Ahorro Verificado</h2>
          <p>Evidencia auditable para entregar a gerencia o al contador.</p>
        </div>
        <div className="card-head-tools">
          <label className="page-size">
            <span>Período</span>
            <input
              type="month"
              value={month || data?.month || ""}
              onChange={(event) => setMonth(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="button ghost small"
            onClick={() => downloadFile(`/api/insights/savings/verified.csv${query}`, "ahorro_verificado.csv")}
          >
            <DownloadIcon /> CSV
          </button>
          <button
            type="button"
            className="button primary small"
            onClick={() => downloadFile(`/api/insights/savings/verified.pdf${query}`, "ahorro_verificado.pdf")}
          >
            <DownloadIcon /> Informe PDF
          </button>
        </div>
      </div>

      {error ? <div className="alert error">{error}</div> : null}

      <div className="verified-summary">
        <div>
          <span>Ahorro verificado del período</span>
          <strong>{formatMoney(data?.total_amount || 0, data?.currency || "CLP")}</strong>
        </div>
        <div>
          <span>Ahorros registrados</span>
          <strong>{data?.count ?? 0}</strong>
        </div>
        <div>
          <span>Período</span>
          <strong>{data?.month || month || "—"}</strong>
        </div>
      </div>

      {loading && !data ? <p className="muted small">Cargando evidencia…</p> : null}

      {!loading && items.length === 0 ? (
        <div className="audit-empty">
          <CheckIcon />
          <h3>Sin ahorros verificados este período</h3>
          <p>Cuando cierres una negociación, registra el ahorro con su evidencia.</p>
        </div>
      ) : null}

      {items.length ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Proveedor</th>
                <th className="right">Antes</th>
                <th className="right">Después</th>
                <th className="right">Cantidad</th>
                <th className="right">Ahorro</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{formatDate(item.realized_at)}</td>
                  <td>
                    <strong>{item.product || item.title || "—"}</strong>
                    <div className="muted small">{item.sku || "Sin SKU"}</div>
                  </td>
                  <td>
                    {item.supplier_before || "—"}
                    {item.supplier_after ? <div className="muted small">→ {item.supplier_after}</div> : null}
                  </td>
                  <td className="right mono">
                    {item.unit_price_before !== null
                      ? formatMoney(item.unit_price_before, item.currency)
                      : "—"}
                  </td>
                  <td className="right mono">
                    {item.unit_price_after !== null
                      ? formatMoney(item.unit_price_after, item.currency)
                      : "—"}
                  </td>
                  <td className="right">{item.quantity ?? "—"}</td>
                  <td className="right mono">{formatMoney(item.realized_amount, item.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
