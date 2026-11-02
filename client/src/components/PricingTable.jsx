import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { CheckIcon } from "./Icons";

const HIGHLIGHTED_PLAN = "pro";

export default function PricingTable({
  currentPlanId = "",
  busyPlanId = "",
  onSelect,
  actionLabel = "Comenzar",
  title = "Planes claros, sin sorpresas",
  subtitle = "Elige el volumen que necesitas y cambia cuando tu operación crezca.",
}) {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api("/api/billing/plans")
      .then((data) => {
        if (active) setPlans(data || []);
      })
      .catch((err) => {
        if (active) setError(err.message || "No se pudieron cargar los planes.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="pricing-section">
      <div className="pricing-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>

      {error ? <div className="alert error">{error}</div> : null}

      <div className="pricing-grid">
        {loading ? <div className="empty-state">Cargando planes…</div> : null}
        {plans.map((plan) => {
          const current = plan.id === currentPlanId;
          const highlighted = plan.id === HIGHLIGHTED_PLAN;
          const busy = busyPlanId === plan.id;
          return (
            <article
              key={plan.id}
              className={`pricing-card ${highlighted ? "featured" : ""} ${current ? "current" : ""}`}
            >
              {highlighted ? <span className="pricing-flag">Más popular</span> : null}

              <header>
                <h3>{plan.name}</h3>
                <p>{plan.description}</p>
              </header>

              <div className="pricing-price">
                {formatMoney(plan.price_monthly, plan.currency)}
                <small>/ mes</small>
              </div>

              <div className="pricing-limit">
                {plan.document_limit === null
                  ? "Documentos ilimitados"
                  : `${plan.document_limit} documentos al mes`}
              </div>

              <ul className="pricing-features">
                {(plan.features || []).map((feature) => (
                  <li key={feature}>
                    <CheckIcon />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className={`button full ${highlighted ? "primary" : "ghost"}`}
                disabled={current || busy}
                onClick={() => onSelect?.(plan)}
              >
                {current ? "Plan actual" : busy ? "Procesando…" : `${actionLabel} ${plan.name}`}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
