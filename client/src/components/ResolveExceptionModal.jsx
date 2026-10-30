import { useState } from "react";
import { api } from "../lib/api";
import { formatMoney, labelize } from "../lib/format";
import { CloseIcon } from "./Icons";

function initialCorrections(exception) {
  return {
    sku: exception.item_sku || "",
    original_description: exception.item_description || "",
    original_unit: exception.item_original_unit || "",
    quantity: exception.item_quantity ?? "",
    original_unit_price: exception.item_original_unit_price ?? "",
    currency: exception.item_currency || "CLP",
  };
}

export default function ResolveExceptionModal({ exception, onClose, onResolved }) {
  const [action, setAction] = useState("approve");
  const [corrections, setCorrections] = useState(initialCorrections(exception));
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update(field, value) {
    setCorrections((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const payload = { action, notes: notes.trim() || null };
      if (action === "correct") {
        payload.corrections = {
          sku: corrections.sku || null,
          original_description: corrections.original_description || null,
          original_unit: corrections.original_unit || null,
          quantity: corrections.quantity === "" ? null : corrections.quantity,
          original_unit_price:
            corrections.original_unit_price === "" ? null : corrections.original_unit_price,
          currency: corrections.currency || null,
        };
      }
      const data = await api(`/api/exceptions/${exception.id}/resolve`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      onResolved?.(data);
    } catch (err) {
      setError(err.message || "No se pudo resolver la excepción.");
    } finally {
      setSubmitting(false);
    }
  }

  const evidence = exception.evidence || {};
  const editable = Boolean(exception.item_id);
  const actions = [
    ["approve", "Aprobar tal cual"],
    ...(editable ? [["correct", "Corregir datos"]] : []),
    ["reject", "Rechazar ítem"],
  ];

  return (
    <div className="modal-overlay" role="presentation" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="eyebrow">Revisión humana</div>
            <h2>{labelize(exception.type)}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            <CloseIcon />
          </button>
        </div>

        <div className="modal-body">
          <div className="evidence-box">
            <div className="evidence-row">
              <span>Proveedor</span>
              <strong>{exception.supplier_name || "Sin proveedor"}</strong>
            </div>
            <div className="evidence-row">
              <span>Documento</span>
              <strong>{exception.document_filename}</strong>
            </div>
            <div className="evidence-row">
              <span>Ítem</span>
              <strong>{exception.item_description || "Documento completo"}</strong>
            </div>
            {evidence.historical_median ? (
              <div className="evidence-row">
                <span>Mediana histórica</span>
                <strong>{formatMoney(evidence.historical_median, exception.item_currency)}</strong>
              </div>
            ) : null}
            {evidence.pct_change !== undefined && evidence.pct_change !== null ? (
              <div className="evidence-row">
                <span>Variación detectada</span>
                <strong>{Number(evidence.pct_change).toFixed(1)}%</strong>
              </div>
            ) : null}
            {typeof evidence.confidence === "number" ? (
              <div className="evidence-row">
                <span>Confianza</span>
                <strong>{Number(evidence.confidence).toFixed(2)}</strong>
              </div>
            ) : null}
          </div>

          <p className="modal-reason">{exception.reason}</p>

          <form onSubmit={handleSubmit}>
            <div className="action-grid">
              {actions.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`action-choice ${action === value ? "selected" : ""}`}
                  onClick={() => setAction(value)}
                >
                  {label}
                </button>
              ))}
            </div>

            {action === "correct" && editable ? (
              <div className="form-grid corrections">
                <label className="field">
                  <span>SKU</span>
                  <input
                    value={corrections.sku}
                    onChange={(event) => update("sku", event.target.value)}
                    placeholder="SKU del proveedor"
                  />
                </label>
                <label className="field">
                  <span>Unidad original</span>
                  <input
                    value={corrections.original_unit}
                    onChange={(event) => update("original_unit", event.target.value)}
                    placeholder="caja, kg, unidad…"
                  />
                </label>
                <label className="field span-2">
                  <span>Descripción</span>
                  <input
                    value={corrections.original_description}
                    onChange={(event) => update("original_description", event.target.value)}
                  />
                </label>
                <label className="field">
                  <span>Cantidad</span>
                  <input
                    type="number"
                    step="any"
                    value={corrections.quantity}
                    onChange={(event) => update("quantity", event.target.value)}
                  />
                </label>
                <label className="field">
                  <span>Precio unitario</span>
                  <input
                    type="number"
                    step="any"
                    value={corrections.original_unit_price}
                    onChange={(event) => update("original_unit_price", event.target.value)}
                  />
                </label>
                <label className="field">
                  <span>Moneda</span>
                  <select
                    value={corrections.currency}
                    onChange={(event) => update("currency", event.target.value)}
                  >
                    <option value="CLP">CLP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="PEN">PEN</option>
                  </select>
                </label>
              </div>
            ) : null}

            <label className="field">
              <span>Nota de revisión</span>
              <textarea
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Explica brevemente la decisión (opcional)."
              />
            </label>

            {error ? <div className="alert error">{error}</div> : null}

            <div className="modal-actions">
              <button type="button" className="button ghost" onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" className="button primary" disabled={submitting}>
                {submitting ? "Guardando…" : "Confirmar revisión"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
