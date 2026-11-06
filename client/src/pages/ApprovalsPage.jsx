import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDateTime, formatMoney, labelize } from "../lib/format";
import { CheckIcon, PlusIcon, XIcon } from "../components/Icons";

const EMPTY_FORM = {
  title: "",
  amount: "",
  currency: "CLP",
  priority: "normal",
  supplier_id: "",
  notes: "",
};

export default function ApprovalsPage() {
  const { canManage, canOperate, organization } = useAuth();
  const [approvals, setApprovals] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [status, setStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [approvalData, supplierData] = await Promise.all([
        api(`/api/enterprise/approvals?status=${encodeURIComponent(status)}&page_size=100`),
        api("/api/suppliers"),
      ]);
      setApprovals(approvalData.items || []);
      setSuppliers(supplierData.items || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las aprobaciones.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  async function createApproval(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api("/api/enterprise/approvals", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          amount: Number(form.amount),
          currency: form.currency || organization?.default_currency || "CLP",
          supplier_id: form.supplier_id || null,
        }),
      });
      setSuccess("Solicitud de compra creada.");
      setForm(EMPTY_FORM);
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear la aprobación.");
    } finally {
      setPending(false);
    }
  }

  async function decide(approval, nextStatus) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api(`/api/enterprise/approvals/${approval.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ status: nextStatus }),
      });
      setSuccess(nextStatus === "approved" ? "Compra aprobada." : "Compra rechazada.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo registrar la decisión.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Gobierno de compras</div>
          <h2>Aprobaciones</h2>
          <p>Controla solicitudes de compra, montos y responsables antes de emitir la orden.</p>
        </div>
        {canOperate ? (
          <button
            type="button"
            className="button primary"
            onClick={() => setShowForm((value) => !value)}
          >
            <PlusIcon /> Nueva solicitud
          </button>
        ) : null}
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      {showForm ? (
        <form className="card" onSubmit={createApproval}>
          <div className="card-head">
            <div>
              <h2>Nueva solicitud</h2>
              <p>Quedará pendiente de aprobación de un administrador.</p>
            </div>
            <button type="button" className="icon-button" onClick={() => setShowForm(false)}>
              <XIcon />
            </button>
          </div>
          <div className="form-grid">
            <label className="form-field">
              <span>Título *</span>
              <input
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Compra de insumos julio"
                required
              />
            </label>
            <label className="form-field">
              <span>Monto *</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.amount}
                onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                required
              />
            </label>
            <label className="form-field">
              <span>Moneda</span>
              <select
                value={form.currency}
                onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))}
              >
                {["CLP", "USD", "EUR", "PEN", "COP", "MXN", "BRL", "ARS"].map((currency) => (
                  <option key={currency} value={currency}>{currency}</option>
                ))}
              </select>
            </label>
            <label className="form-field">
              <span>Prioridad</span>
              <select
                value={form.priority}
                onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value }))}
              >
                <option value="low">Baja</option>
                <option value="normal">Normal</option>
                <option value="high">Alta</option>
                <option value="urgent">Urgente</option>
              </select>
            </label>
            <label className="form-field">
              <span>Proveedor</span>
              <select
                value={form.supplier_id}
                onChange={(event) => setForm((current) => ({ ...current, supplier_id: event.target.value }))}
              >
                <option value="">Sin proveedor</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
                ))}
              </select>
            </label>
            <label className="form-field form-field-wide">
              <span>Notas</span>
              <textarea
                rows={3}
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Contexto, centro de costo o condiciones relevantes."
              />
            </label>
          </div>
          <div className="form-actions">
            <button type="button" className="button ghost" onClick={() => setShowForm(false)} disabled={pending}>
              Cancelar
            </button>
            <button type="submit" className="button primary" disabled={pending}>
              {pending ? "Creando…" : "Crear solicitud"}
              <CheckIcon />
            </button>
          </div>
        </form>
      ) : null}

      <div className="card">
        <div className="table-toolbar">
          <div className="card-head">
            <div>
              <h2>Solicitudes</h2>
              <p>{approvals.length} registro(s) en la vista actual.</p>
            </div>
          </div>
          <label className="page-size">
            <span>Estado</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="pending">Pendientes</option>
              <option value="approved">Aprobadas</option>
              <option value="rejected">Rechazadas</option>
              <option value="cancelled">Canceladas</option>
            </select>
          </label>
        </div>

        {loading ? (
          <div className="empty-state">Cargando solicitudes…</div>
        ) : approvals.length === 0 ? (
          <div className="empty-state">
            <p>No hay solicitudes en este estado.</p>
            {canOperate ? (
              <button type="button" className="button primary" onClick={() => setShowForm(true)}>
                <PlusIcon /> Crear la primera
              </button>
            ) : null}
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Prioridad</th>
                  <th>Solicitud</th>
                  <th>Proveedor</th>
                  <th>Monto</th>
                  <th>Solicitante</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {approvals.map((approval) => (
                  <tr key={approval.id}>
                    <td>
                      <span className={`badge priority-${approval.priority}`}>{labelize(approval.priority)}</span>
                    </td>
                    <td>
                      <strong>{approval.title}</strong>
                      {approval.notes ? <div className="muted small">{approval.notes}</div> : null}
                    </td>
                    <td>{approval.supplier_name || "—"}</td>
                    <td className="mono">{formatMoney(approval.amount, approval.currency)}</td>
                    <td>{approval.requested_by_name || "—"}</td>
                    <td><span className={`badge status-${approval.status}`}>{labelize(approval.status)}</span></td>
                    <td>{formatDateTime(approval.created_at)}</td>
                    <td>
                      {canManage && approval.status === "pending" ? (
                        <div className="table-actions">
                          <button
                            type="button"
                            className="button ghost small"
                            onClick={() => decide(approval, "approved")}
                            disabled={pending}
                            title="Aprobar"
                          >
                            <CheckIcon /> Aprobar
                          </button>
                          <button
                            type="button"
                            className="button ghost small danger"
                            onClick={() => decide(approval, "rejected")}
                            disabled={pending}
                            title="Rechazar"
                          >
                            <XIcon /> Rechazar
                          </button>
                        </div>
                      ) : (
                        <span className="muted">{approval.decided_by_name || "—"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
