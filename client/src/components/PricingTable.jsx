import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { CheckIcon } from "./Icons";

const HIGHLIGHTED_PLAN = "pro";
const PLAN_FETCH_TIMEOUT_MS = 6000;

// Planes oficiales de respaldo: la landing pública nunca queda vacía ni muestra
// un error si /api/billing/plans tarda o falla de forma temporal.
const FALLBACK_PLANS = [
  {
    id: "free",
    name: "Free",
    description: "Para probar la auditoría con un volumen acotado.",
    price_monthly: 0,
    currency: "CLP",
    document_limit: 25,
    user_limit: 1,
    features: [
      "25 documentos al mes",
      "Auditoría de precios",
      "Dashboard mensual",
      "Exportaciones básicas",
      "1 usuario",
    ],
    sort_order: 10,
  },
  {
    id: "pro",
    name: "Pro",
    description: "Para ferreterías y distribuidores que necesitan control continuo.",
    price_monthly: 39990,
    currency: "CLP",
    document_limit: 500,
    user_limit: 5,
    features: [
      "500 documentos al mes",
      "Hasta 5 usuarios con roles",
      "Alertas de cuota y precio",
      "Exportaciones PDF y Excel",
      "Historial de 12 meses",
      "Copiloto de IA con cuota mensual",
    ],
    sort_order: 20,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "Para operaciones multi-sucursal y alto volumen.",
    price_monthly: 149990,
    currency: "CLP",
    document_limit: null,
    user_limit: null,
    features: [
      "Documentos ilimitados",
      "Usuarios y sucursales ilimitadas",
      "Panel multi-tenant",
      "Auditoría avanzada y RCV",
      "Exportaciones masivas",
      "Gestión centralizada",
    ],
    sort_order: 30,
  },
];

export default function PricingTable({
  currentPlanId = "",
  busyPlanId = "",
  onSelect,
  actionLabel = "Comenzar",
  title = "Planes claros, sin sorpresas",
  subtitle = "Elige el volumen que necesitas y cambia cuando tu operación crezca.",
}) {
  const [plans, setPlans] = useState(FALLBACK_PLANS);
  const [usingFallback, setUsingFallback] = useState(false);

  useEffect(() => {
    let active = true;
    api("/api/billing/plans", { timeoutMs: PLAN_FETCH_TIMEOUT_MS })
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data) && data.length > 0) {
          setPlans(data);
          setUsingFallback(false);
        } else {
          setUsingFallback(true);
        }
      })
      .catch(() => {
        if (active) setUsingFallback(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const visiblePlans = Array.isArray(plans) && plans.length > 0 ? plans : FALLBACK_PLANS;

  return (
    <section className="pricing-section">
      <div className="pricing-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>

      {usingFallback ? (
        <p className="muted-note pricing-fallback-note">
          Mostrando planes de referencia. Los precios se confirman al crear tu cuenta.
        </p>
      ) : null}

      <div className="pricing-grid">
        {visiblePlans.map((plan) => {
          const current = plan.id === currentPlanId;
          const highlighted = plan.id === HIGHLIGHTED_PLAN;
          const busy = busyPlanId === plan.id;
          const features = Array.isArray(plan.features) ? plan.features : [];
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
                {Number(plan.price_monthly) <= 0 ? (
                  "Gratis"
                ) : (
                  <>
                    {formatMoney(plan.price_monthly, plan.currency)}
                    <small> / mes</small>
                  </>
                )}
              </div>

              <div className="pricing-limit">
                {plan.document_limit == null
                  ? "Documentos ilimitados"
                  : `${plan.document_limit} documentos al mes`}
              </div>

              {plan.user_limit !== undefined ? (
                <div className="pricing-limit">
                  {plan.user_limit == null
                    ? "Usuarios ilimitados"
                    : `${plan.user_limit} usuario${Number(plan.user_limit) === 1 ? "" : "s"}`}
                </div>
              ) : null}

              <ul className="pricing-features">
                {features.map((feature) => (
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
