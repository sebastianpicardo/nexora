import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatMoney, labelize } from "../lib/format";
import QuotaCard from "../components/QuotaCard";
import { CheckIcon, SparkIcon } from "../components/Icons";

export default function BillingPage() {
  const { refreshBilling } = useAuth();
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [changing, setChanging] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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

  async function changePlan(planId) {
    if (planId === billing?.subscription?.plan_id) return;
    setChanging(planId);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/billing/change-plan", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId }),
      });
      setBilling(data);
      await refreshBilling();
      setSuccess(`Plan actualizado a ${data.subscription.plan_name}.`);
    } catch (err) {
      setError(err.message || "No se pudo cambiar de plan.");
    } finally {
      setChanging("");
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

      <div className="billing-grid">
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Consumo actual</h2>
              <p>El ciclo se reinicia automáticamente cada mes.</p>
            </div>
            <span className="soft-chip">{subscription?.plan_name || "Free"}</span>
          </div>
          <QuotaCard quota={billing?.usage} planName={subscription?.plan_name || "Free"} />
          <div className="billing-meta">
            <div>
              <span>Inicio del ciclo</span>
              <strong>{formatDate(billing?.usage?.period_start)}</strong>
            </div>
            <div>
              <span>Próxima renovación</span>
              <strong>{formatDate(billing?.usage?.period_end)}</strong>
            </div>
            <div>
              <span>Precio mensual</span>
              <strong>
                {plans.find((plan) => plan.id === subscription?.plan_id)
                  ? formatMoney(
                      plans.find((plan) => plan.id === subscription?.plan_id).price_monthly,
                      plans.find((plan) => plan.id === subscription?.plan_id).currency,
                    )
                  : "—"}
              </strong>
            </div>
          </div>
        </section>

        <section className="card plan-note">
          <div className="eyebrow">Facturación simple</div>
          <h3>Sin cobros ocultos</h3>
          <p>
            Los cambios de plan se aplican al ciclo actual. La integración de pagos se conecta con tu
            proveedor preferido; por ahora el panel administra capacidad y suscripción.
          </p>
          <div className="security-row">
            <CheckIcon />
            <span>Roles y permisos por organización</span>
          </div>
          <div className="security-row">
            <CheckIcon />
            <span>Cuotas y alertas de consumo</span>
          </div>
          <div className="security-row">
            <CheckIcon />
            <span>Exportaciones auditables</span>
          </div>
        </section>
      </div>

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
                  onClick={() => changePlan(plan.id)}
                >
                  {current ? "Plan activo" : changing === plan.id ? "Actualizando…" : `Elegir ${plan.name}`}
                </button>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
