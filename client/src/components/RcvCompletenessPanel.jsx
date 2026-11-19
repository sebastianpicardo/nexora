import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney } from "../lib/format";
import { CheckIcon, UploadIcon } from "./Icons";

export default function RcvCompletenessPanel() {
  const { user } = useAuth();
  const canImport = ["owner", "admin", "analyst"].includes(user?.role || "");
  const [period, setPeriod] = useState("");
  const [data, setData] = useState(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const query = period ? `?period=${encodeURIComponent(period)}` : "";
      setData(await api(`/api/leaks/rcv/completeness${query}`));
    } catch (err) {
      setError(err.message || "No se pudo cargar la completitud del RCV.");
    }
  }, [period]);

  useEffect(() => {
    load();
  }, [load]);

  async function register() {
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const form = new FormData();
      form.append("file", file);
      if (period) form.append("period", period);
      const result = await api("/api/leaks/rcv/register", { method: "POST", body: form });
      setNotice(
        `RCV cargado: ${result.rows} documentos (${result.inserted} nuevos, ${result.updated} actualizados).`,
      );
      setFile(null);
      await load();
    } catch (err) {
      setError(err.message || "No se pudo cargar el RCV.");
    } finally {
      setBusy(false);
    }
  }

  const total = Number(data?.total_documents || 0);
  const pct = Number(data?.completeness_pct || 0);

  return (
    <section className="card rcv-completeness">
      <div className="card-head">
        <div>
          <h2>Completitud SII · RCV</h2>
          <p>Compara lo declarado en el Registro de Compras contra los documentos con detalle.</p>
        </div>
        <label className="page-size">
          <span>Período</span>
          <input
            type="month"
            value={period || data?.period || ""}
            onChange={(event) => setPeriod(event.target.value)}
          />
        </label>
      </div>

      {error ? <div className="alert error">{error}</div> : null}
      {notice ? <div className="alert success">{notice}</div> : null}

      <div className={`rcv-status ${data?.missing ? "warning" : total ? "ok" : "empty"}`}>
        <div>
          <strong>{data?.message || "Cargando estado del RCV…"}</strong>
          <span>
            {total
              ? `${data?.with_detail || 0} con detalle · ${data?.missing || 0} pendientes · ${formatMoney(
                  data?.missing_amount || 0,
                  data?.currency,
                )} sin respaldo`
              : "Aún no hay documentos del RCV cargados."}
          </span>
        </div>
        <div className="rcv-progress" aria-label={`Completitud ${pct}%`}>
          <span style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
        <strong className="rcv-pct">{pct}%</strong>
      </div>

      {canImport ? (
        <div className="rcv-upload">
          <UploadIcon />
          <label className="audit-file">
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <span>{file ? file.name : "Cargar Registro de Compras (CSV/Excel)"}</span>
          </label>
          <button type="button" className="button ghost" disabled={!file || busy} onClick={register}>
            {busy ? "Cargando…" : "Importar RCV"}
          </button>
          <span className="muted small">
            Columnas: Tipo Doc, Folio, Fecha, RUT Proveedor, Razón Social, Neto, IVA, Total.
          </span>
        </div>
      ) : null}

      {data?.missing_documents?.length ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Tipo</th>
                <th>Proveedor</th>
                <th>RUT</th>
                <th>Fecha</th>
                <th className="right">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.missing_documents.map((row) => (
                <tr key={`${row.tipo_doc}-${row.folio}-${row.rut}`}>
                  <td className="mono">{row.folio}</td>
                  <td>{row.tipo_doc}</td>
                  <td>{row.supplier || "—"}</td>
                  <td className="mono">{row.rut || "—"}</td>
                  <td>{row.date ? formatDate(row.date) : "—"}</td>
                  <td className="right mono">{formatMoney(row.total, data.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : total ? (
        <div className="audit-empty">
          <CheckIcon />
          <h3>Sin documentos pendientes</h3>
          <p>Todos los documentos del RCV del período tienen detalle en NEXORA.</p>
        </div>
      ) : null}
    </section>
  );
}
