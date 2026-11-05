/* ------------------------------------------------------------------
   BillingPage – facturación completa: planes, checkout, facturas, cancelación
   ------------------------------------------------------------------ */
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, labelize } from "../lib/format";
import QuotaCard from "../components/QuotaCard";
import { CheckIcon, SparkIcon, ArrowRightIcon, DownloadIcon, TrashIcon } from "../components/Icons";

export default function BillingPage() {
  const { refreshBilling } = useAuth();
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [changing, setChanging] = useState("");
  const [pendingPlan, setPendingPlan] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [invoices, setInvoices] = useState([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [showInvoices, setShowInvoices] = useState(false);
  const [cancelConfirm, setCancelConfirm] = useState(false);

  /* ------------------------------------------------------------------
     Cargar resumen de facturación
     ------------------------------------------------------------------ */
  const load = useCallback(async () => {
    try {
      const data = await api("/api/billing/summary");
      setBilling(data);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudo cargar la facturación.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const checkout = params.get("checkout");
    if (!checkout) return;
    if (checkout === "success") {
      setSuccess("Pago recibido. Estamos actualizando tu suscripción…");
      refreshBilling();
    } else if (checkout === "cancel") {
      setError("El proceso de pago fue cancelado.");
    }
    params.delete("checkout");
    params.delete("provider");
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  }, [refreshBilling]);

  /* ------------------------------------------------------------------
     Iniciar checkout (Stripe / Mercado Pago / Flow / mock)
     ------------------------------------------------------------------ */
  const startPlan = async (plan) => {
    if (plan.id === billing?.subscription?.plan_id) return;

    let session;
    try {
      session = await api("/api/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_id: plan.id }),
      });
    } catch (err) {
      setError(err.message || "No se pudo iniciar el pago.");
      return;
    }

    if (session.provider === "mock") {
      setPendingPlan(plan);
      return;
    }

    // Backend devuelve checkout_url (no url)
    if (session.checkout_url) {
      window.location.assign(session.checkout_url);
      return;
    }

    setError("Respuesta de pago inesperada.");
  };

  /* ------------------------------------------------------------------
     Aplicar plan (solo free / mock confirmed)
     ------------------------------------------------------------------ */
  async function applyPlan(planId) {
    setChanging(planId);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/billing/change-plan", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId }),
      });
      setBilling(data);
      setPendingPlan(null);
      await refreshBilling();
      setSuccess(`Plan actualizado a ${data.subscription.plan_name}.`);
    } catch (err) {
      setError(err.message || "No se pudo cambiar de plan.");
    } finally {
      setChanging("");
    }
  }

  /* ------------------------------------------------------------------
     Cancelar suscripción
     ------------------------------------------------------------------ */
  async function cancelSubscription() {
    setError("");
    setSuccess("");
    setChanging("cancel");
    try {
      const data = await api("/api/billing/subscription/cancel", {
        method: "POST",
      });
      setBilling(data);
      await refreshBilling();
      setSuccess("Suscripción cancelada. El plan gratuito se activará al fin del período.");
    } catch (err) {
      setError(err.message || "No se pudo cancelar la suscripción.");
    } finally {
      setChanging("");
    }
  }

  /* ------------------------------------------------------------------
     Cargar facturas
     ------------------------------------------------------------------ */
  async function loadInvoices() {
    setInvoicesLoading(true);
    try {
      const data = await api("/api/billing/invoices");
      setInvoices(data.items || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las facturas.");
    } finally {
      setInvoicesLoading(false);
    }
  }

  async function downloadInvoicePdf(invoiceId) {
    try {
      const blob = await api.raw("/api/billing/invoices/" + invoiceId + "/pdf", {
        method: "GET",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `factura-${invoiceId}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "No se pudo descargar la factura.");
    }
  }

  const subscription = billing?.subscription;
  const plans = billing?.plans || [];

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><SparkIcon /> Suscripción</div>
          <h2>Plan y facturación</h2>
          <p>Controla la capacidad mensual, el consumo del equipo y el plan activo de tu organización.</p>
        </div>
        <span className={`badge role-${subscription?.status || "active"}`}>
          {labelize(subscription?.status || "active")}
        </span>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      {/* --------------------------------------------------------------
         Flujo real de pago (Stripe / Mercado Pago / Flow / mock)
         -------------------------------------------------------------- */}
      {pendingPlan ? (
        <section className="card mock-checkout">
          <div>
            <h3>Pago de prueba · {pendingPlan.name}</h3>
            <p>
              El proveedor está en modo <code>mock</code>. Confirma para activar
              el plan sin realizar un cobro real.
            </p>
          </div>
          <div className="mock-checkout-actions">
            <button type="button" className="button ghost" onClick={() => setPendingPlan(null)}>
              Cancelar
            </button>
            <button
              type="button"
              className="button primary"
              disabled={Boolean(changing)}
              onClick={() => applyPlan(pendingPlan.id)}
            >
              Confirmar pago
            </button>
          </div>
        </section>
      ) : null}

      {/* --------------------------------------------------------------
         Planes disponibles
         -------------------------------------------------------------- */}
      <section>
        <div className="section-heading">
          <div>
            <h2>Planes disponibles</h2>
            <p>Escala la operación sin cambiar tus flujos de auditoría.</p>
          </div>
        </div>
        <div className="plan-grid">
          {loading ? <div className="empty-state">Cargando planes…</div> : null}
          {plans.map((plan) => {
            const current = plan.id === subscription?.plan_id;
            return (
              <article key={plan.id} className={`plan-card ${current ? "current" : ""}`}>
                {current ? <span className="plan-flag">Plan actual</span> : null}
                <div className="plan-name">{plan.name}</div>
                <p className="plan-description">{plan.description}</p>
                <div className="plan-price">
                  {formatMoney(plan.price_monthly, plan.currency)}
                  <small>/ mes</small>
                </div>
                <div className="plan-limit">
                  {plan.document_limit === null
                    ? "Documentos ilimitados"
                    : `${plan.document_limit} documentos al mes`}
                </div>
                <ul className="plan-features">
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <CheckIcon />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className={`button ${current ? "ghost" : "primary"} full`}
                  disabled={current || changing === plan.id}
                  onClick={() => startPlan(plan)}
                >
                  {current ? "Plan activo" : changing === plan.id ? "Actualizando…" : `Elegir ${plan.name}`}
                </button>
              </article>
            );
          })}
        </div>
      </section>

      {/* --------------------------------------------------------------
         Facturas / Recibos
         -------------------------------------------------------------- */}
      <section>
        <div className="section-heading">
          <div>
            <h2>Facturas y recibos</h2>
            <p>Historial de pagos y documentos fiscales.</p>
          </div>
          <button
            type="button"
            className="button secondary"
            onClick={() => { setShowInvoices(!showInvoices); if (!showInvoices) loadInvoices(); }}
          >
            {showInvoices ? "Ocultar" : "Ver facturas"}
            <ArrowRightIcon />
          </button>
        </div>
        {showInvoices && (
          <div className="invoices-section">
            {invoicesLoading ? (
              <div className="empty-state">Cargando facturas…</div>
            ) : invoices.length === 0 ? (
              <div className="empty-state">No hay facturas aún.</div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Proveedor</th>
                      <th>Monto</th>
                      <th>Moneda</th>
                      <th>Estado</th>
                      <th>Período</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((inv) => (
                      <tr key={inv.id}>
                        <td>{formatDate(inv.created_at)}</td>
                        <td>{inv.provider}</td>
                        <td>{formatMoney(inv.amount, inv.currency)}</td>
                        <td>{inv.currency}</td>
                        <td><span className={`badge role-${inv.status}`}>{labelize(inv.status)}</span></td>
                        <td>
                          {inv.period_start && inv.period_end
                            ? `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`
                            : "—"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="button ghost icon-only"
                            onClick={() => downloadInvoicePdf(inv.id)}
                            title="Descargar PDF"
                          >
                            <DownloadIcon />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>

      {/* --------------------------------------------------------------
         Cancelar suscripción (solo owner/admin, plan pago activo)
         -------------------------------------------------------------- */}
      {subscription && subscription.plan_id !== "free" && subscription.status === "active" && (
        <section className="card danger-zone">
          <div>
            <h3>Cancelar suscripción</h3>
            <p>
              La suscripción se cancelará al final del período actual. No se realizarán más cobros.
              El plan volverá a <strong>Free</strong> automáticamente.
            </p>
          </div>
          {!cancelConfirm ? (
            <button
              type="button"
              className="button danger"
              onClick={() => setCancelConfirm(true)}
            >
              Cancelar suscripción
            </button>
          ) : (
            <div className="mock-checkout-actions">
              <button type="button" className="button ghost" onClick={() => setCancelConfirm(false)}>
                Volver
              </button>
              <button
                type="button"
                className="button danger"
                disabled={changing === "cancel"}
                onClick={cancelSubscription}
              >
                {changing === "cancel" ? "Cancelando…" : "Confirmar cancelación"}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}