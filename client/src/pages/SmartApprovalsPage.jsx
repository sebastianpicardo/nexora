import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, formatNumber, percent } from "../lib/format";
import StatCard from "../components/StatCard";
import { CheckIcon, ClockIcon, ExceptionsIcon, SparkIcon } from "../components/Icons";

const THRESHOLD_OPTIONS = [0.7, 0.75, 0.8, 0.85, 0.9, 0.95];

export default function SmartApprovalsPage() {
  const { organization, canOperate } = useAuth();
  const [currency, setCurrency] = useState(organization?.default_currency || "CLP");
  const [threshold, setThreshold] = useState(0.9);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selected, setSelected] = useState([]);

  useEffect(() => {
    if (organization?.default_currency) setCurrency(organization.default_currency);
  }, [organization?.default_currency]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        currency,
        threshold: String(threshold),
        days: "180",
      });
      const result = await api(`/api/insights/approvals?${params.toString()}`);
      setData(result);
      setSelected([]);
    } catch (err) {
      setError(err.message || "No se pudo cargar la cola de aprobación.");
    } finally {
      setLoading(false);
    }
  }, [currency, threshold]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = data?.summary || {};
  const items = data?.items || [];
  const eligible = items.filter((row) => row.auto_eligible);
  const allEligibleSelected =
    eligible.length > 0 && eligible.every((row) => selected.includes(row.id));

  function toggle(id) {
    setSelected((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  function toggleAll() {
    setSelected(allEligibleSelected ? [] : eligible.map((row) => row.id));
  }

  async function approve(itemIds) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const result = await api("/api/insights/auto-approve", {
        method: "POST",
        body: JSON.stringify({ threshold, item_ids: itemIds || null }),
      });
      setSuccess(
        result.approved > 0
          ? `${result.approved} ítem(s) auto-aprobados con confianza ≥ ${Math.round(threshold * 100)}%.`
          : "No había ítems elegibles para auto-aprobar.",
      );
      load();
    } catch (err) {
      setError(err.message || "No se pudo ejecutar la auto-aprobación.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><SparkIcon /> Automatización</div>
          <h2>Aprobación inteligente</h2>
          <p>
            Auto-aprueba ítems con alta confianza y sin excepciones críticas. El resto queda en
            revisión manual para el equipo de compras.
          </p>
        </div>
        <div className="card-head-tools">
          <label className="page-size">
            <span>Confianza mínima</span>
            <select
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
            >
              {THRESHOLD_OPTIONS.map((option) => (
                <option key={option} value={option}>{Math.round(option * 100)}%</option>
              ))}
            </select>
          </label>
          <label className="page-size">
            <span>Moneda</span>
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              {["CLP", "USD", "EUR", "PEN", "COP", "MXN", "BRL", "ARS"].map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          {canOperate ? (
            <button
              type="button"
              className="button primary"
              onClick={() => approve(selected.length ? selected : null)}
              disabled={pending || (eligible.length === 0 && selected.length === 0)}
            >
              <CheckIcon />
              {selected.length ? `Aprobar ${selected.length}` : "Auto-aprobar elegibles"}
            </button>
          ) : null}
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <section className="stats-grid">
        <StatCard
          label="Pendientes"
          value={loading ? "—" : summary.pending ?? 0}
          detail="Ítems esperando decisión"
          icon={<ClockIcon />}
        />
        <StatCard
          label="Auto-aprobables"
          value={loading ? "—" : summary.auto_eligible ?? 0}
          detail={`Confianza ≥ ${Math.round(threshold * 100)}% sin alertas críticas`}
          tone="ok"
          icon={<CheckIcon />}
        />
        <StatCard
          label="Requieren revisión"
          value={loading ? "—" : summary.needs_review ?? 0}
          detail="Baja confianza o excepciones activas"
          tone="warning"
          icon={<ExceptionsIcon />}
        />
        <StatCard
          label="Monto auto-aprobable"
          value={formatMoney(summary.auto_amount || 0, currency)}
          detail={`Revisión manual: ${formatMoney(summary.review_amount || 0, currency)}`}
          tone="brand"
          icon={<SparkIcon />}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Cola de aprobación</h2>
            <p>Ítems pendientes con su nivel de confianza y excepciones asociadas.</p>
          </div>
          <span className="badge">{items.length} ítem(s)</span>
        </div>
        {loading ? (
          <div className="empty-state">Cargando cola…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p>No hay ítems pendientes de aprobación.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={allEligibleSelected}
                      onChange={toggleAll}
                      aria-label="Seleccionar auto-aprobables"
                      disabled={eligible.length === 0}
                    />
                  </th>
                  <th>Producto</th>
                  <th>Proveedor</th>
                  <th>Documento</th>
                  <th>Cantidad</th>
                  <th>Precio</th>
                  <th>Monto</th>
                  <th>Confianza</th>
                  <th>Excepciones</th>
                  <th>Decisión</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.includes(row.id)}
                        onChange={() => toggle(row.id)}
                        disabled={!row.auto_eligible}
                        aria-label={`Seleccionar ${row.description || row.id}`}
                      />
                    </td>
                    <td>
                      <strong>{row.description || row.sku || "Ítem"}</strong>
                      <div className="muted small">{row.base_unit || "unidad"}</div>
                    </td>
                    <td>{row.supplier_name || "—"}</td>
                    <td className="truncate">{row.document_filename || "—"}</td>
                    <td>{formatNumber(row.quantity, 2)}</td>
                    <td className="mono">{formatMoney(row.unit_price, currency)}</td>
                    <td className="mono">{formatMoney(row.amount, currency)}</td>
                    <td>{percent(row.confidence * 100, 1)}</td>
                    <td>
                      {row.high_severity_exceptions > 0 ? (
                        <span className="badge status-rejected">{row.high_severity_exceptions} crítica(s)</span>
                      ) : row.pending_exceptions > 0 ? (
                        <span className="badge priority-high">{row.pending_exceptions} pendiente(s)</span>
                      ) : (
                        <span className="badge status-approved">Sin alertas</span>
                      )}
                    </td>
                    <td>
                      {row.auto_eligible ? (
                        <span className="badge status-approved">Auto-aprobable</span>
                      ) : (
                        <span className="badge status-pending">Revisión manual</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Cómo funciona</h2>
            <p>Regla aplicada a los ítems pendientes de los últimos 180 días.</p>
          </div>
        </div>
        <ul className="stack" style={{ paddingLeft: 18, margin: 0 }}>
          <li>
            Se auto-aprueban los ítems con confianza de extracción ≥ {Math.round(threshold * 100)}%.
          </li>
          <li>No deben tener excepciones pendientes de severidad alta o crítica.</li>
          <li>Los ítems con alertas o baja confianza permanecen en revisión manual.</li>
          <li>Cada auto-aprobación queda registrada en la auditoría de la organización.</li>
        </ul>
      </section>
    </div>
  );
}
