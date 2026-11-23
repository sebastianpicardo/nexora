import { useCallback, useEffect, useState } from "react";
import { api, downloadFile } from "../lib/api";
import { formatDate, formatMoney } from "../lib/format";
import { DownloadIcon, SearchIcon, UploadIcon } from "./Icons";

export default function CompraAgilPanel() {
  const [data, setData] = useState(null);
  const [search, setSearch] = useState("");
  const [file, setFile] = useState(null);
  const [quote, setQuote] = useState(null);
  const [selected, setSelected] = useState("");
  const [margin, setMargin] = useState(25);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = search ? `?q=${encodeURIComponent(search)}` : "";
      setData(await api(`/api/compra-agil/opportunities${query}`));
    } catch (err) {
      setError(err.message || "No se pudo cargar el radar de Compra Ágil.");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  const opportunities = data?.opportunities || [];
  const catalogMatches = data?.catalog_matches || [];
  const mode = data?.mode || "manual";

  async function importFile() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/api/compra-agil/import", { method: "POST", body: form });
      setFile(null);
      await load();
    } catch (err) {
      setError(err.message || "No se pudo importar el archivo.");
    } finally {
      setBusy(false);
    }
  }

  async function loadQuote(externalId) {
    setSelected(externalId);
    setQuote(null);
    setError("");
    try {
      setQuote(await api(`/api/compra-agil/${encodeURIComponent(externalId)}/quote?target_margin=${margin}`));
    } catch (err) {
      setError(err.message || "No se pudo generar la cotización.");
    }
  }

  return (
    <div className="page-stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Radar Compra Ágil</h2>
            <p>
              Oportunidades públicas de hasta 100 UTM cruzadas con tu catálogo y mejor costo
              registrado.
            </p>
          </div>
          <label className="search-field">
            <SearchIcon />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar comprador, título o código"
            />
          </label>
        </div>

        {error ? <div className="alert error">{error}</div> : null}
        <div className={`radar-mode ${mode === "api" ? "api" : "manual"}`}>
          <strong>
            {mode === "api" ? "API conectada" : mode === "catalog" ? "Coincidencias en catálogo" : "Modo manual"}
          </strong>
          <span>{data?.message}</span>
        </div>

        <div className="radar-import">
          <UploadIcon />
          <label className="audit-file">
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <span>{file ? file.name : "Cargar oportunidades CSV/Excel"}</span>
          </label>
          <button type="button" className="button ghost" disabled={!file || busy} onClick={importFile}>
            {busy ? "Importando…" : "Importar"}
          </button>
          <span className="muted small">
            Columnas: Código, Título, Comprador, Cierre, Ítem, Unidad, Cantidad, SKU.
          </span>
        </div>

        {loading && !data ? <p className="muted small">Cargando oportunidades…</p> : null}

        {!loading && opportunities.length === 0 && catalogMatches.length === 0 ? (
          <div className="audit-empty">
            <SearchIcon />
            <h3>Sin oportunidades cargadas</h3>
            <p>
              Importa un CSV o configura COMPRA_AGIL_API_URL y COMPRA_AGIL_API_KEY para consultar
              la API. También puedes buscar por producto para ver coincidencias en tu catálogo.
            </p>
          </div>
        ) : null}

        {catalogMatches.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Producto en tu catálogo</th>
                  <th>Proveedor</th>
                  <th className="right">Mejor precio</th>
                </tr>
              </thead>
              <tbody>
                {catalogMatches.map((row, index) => (
                  <tr key={`${row.sku || row.product}-${index}`}>
                    <td className="mono">{row.sku || "—"}</td>
                    <td>
                      <strong>{row.product}</strong>
                      <div className="muted small">{row.unit}</div>
                    </td>
                    <td>{row.supplier || "—"}</td>
                    <td className="right mono">
                      {row.price != null ? formatMoney(row.price, "CLP") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {opportunities.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Oportunidad</th>
                  <th>Comprador</th>
                  <th>Cierre</th>
                  <th className="right">Ítems</th>
                  <th className="right">Presupuesto</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {opportunities.map((row) => (
                  <tr key={row.external_id}>
                    <td className="mono">{row.external_id}</td>
                    <td>
                      <strong>{row.title}</strong>
                      <div className="muted small">{row.region || row.status}</div>
                    </td>
                    <td>{row.buyer || "—"}</td>
                    <td>{row.closes_at ? formatDate(row.closes_at) : "—"}</td>
                    <td className="right">{row.item_count ?? 0}</td>
                    <td className="right mono">
                      {row.budget_clp ? formatMoney(row.budget_clp, "CLP") : "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="button ghost small"
                        onClick={() => loadQuote(row.external_id)}
                      >
                        Cotizar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {selected ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Propuesta de cotización</h2>
              <p>{quote?.opportunity?.title || selected}</p>
            </div>
            <div className="card-head-tools">
              <label className="page-size">
                <span>Margen objetivo</span>
                <input
                  type="number"
                  min="0"
                  max="90"
                  value={margin}
                  onChange={(event) => setMargin(Number(event.target.value))}
                />
              </label>
              <button type="button" className="button ghost small" onClick={() => loadQuote(selected)}>
                Recalcular
              </button>
              <button
                type="button"
                className="button primary small"
                disabled={!quote}
                onClick={() =>
                  downloadFile(
                    `/api/compra-agil/${encodeURIComponent(selected)}/quote.csv?target_margin=${margin}`,
                    `cotizacion_${selected}.csv`,
                  )
                }
              >
                <DownloadIcon /> Exportar
              </button>
            </div>
          </div>

          {quote ? (
            <>
              <div className="verified-summary">
                <div>
                  <span>Costo real</span>
                  <strong>{formatMoney(quote.total_cost, quote.currency)}</strong>
                </div>
                <div>
                  <span>Oferta total</span>
                  <strong>{formatMoney(quote.total_offer, quote.currency)}</strong>
                </div>
                <div>
                  <span>Margen bruto</span>
                  <strong>{formatMoney(quote.gross_margin, quote.currency)}</strong>
                </div>
              </div>

              {quote.missing > 0 ? (
                <div className="alert warning">
                  {quote.missing} ítem(s) sin costo registrado. Carga una factura o lista de precios
                  para completar la propuesta.
                </div>
              ) : null}

              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th>Unidad</th>
                      <th className="right">Cantidad</th>
                      <th className="right">Costo real</th>
                      <th className="right">Oferta</th>
                      <th className="right">Total</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quote.lines.map((line, index) => (
                      <tr key={`${line.product}-${index}`}>
                        <td>
                          <strong>{line.product}</strong>
                          <div className="muted small">{line.sku || "Sin SKU"}</div>
                        </td>
                        <td>{line.unit}</td>
                        <td className="right">{line.quantity}</td>
                        <td className="right mono">
                          {line.cost_price !== null ? formatMoney(line.cost_price, quote.currency) : "—"}
                        </td>
                        <td className="right mono">
                          {line.offer_price !== null ? formatMoney(line.offer_price, quote.currency) : "—"}
                        </td>
                        <td className="right mono">
                          {line.total !== null ? formatMoney(line.total, quote.currency) : "—"}
                        </td>
                        <td>
                          <span className={`badge ${line.status === "ok" ? "status-processed" : "severity-medium"}`}>
                            {line.status === "ok" ? "Listo" : "Sin costo"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="muted small">Generando propuesta…</p>
          )}
        </section>
      ) : null}
    </div>
  );
}
