import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { CheckIcon, DollarIcon, ShieldIcon, UsersIcon } from "../components/Icons";

function priceFor(plan) {
  if (Number(plan.price_monthly) <= 0) {
    return { amount: "Gratis", period: "" };
  }
  return { amount: formatMoney(plan.price_monthly, plan.currency), period: " / mes" };
}

function usersFor(plan) {
  if (plan.user_limit === null || plan.user_limit === undefined) return "Usuarios ilimitados";
  const n = Number(plan.user_limit);
  return `${n} usuario${n === 1 ? "" : "s"} incluido${n === 1 ? "" : "s"}`;
}

function docsFor(plan) {
  if (plan.document_limit === null || plan.document_limit === undefined) return "Documentos ilimitados";
  return `${plan.document_limit} documentos / mes`;
}

export default function PricingPage() {
  const { canManage, billing, refreshBilling } = useAuth();
  const [plans, setPlans] = useState([]);
  const [currentPlanId, setCurrentPlanId] = useState("");
  const [mode, setMode] = useState({ provider: "mock", test_mode: true, production: false });
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      const [summary, config] = await Promise.all([
        api("/api/billing/summary"),
        api("/api/billing/config").catch(() => ({ provider: "mock", test_mode: true, production: false })),
      ]);
      setPlans((summary.plans || []).slice().sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)));
      setCurrentPlanId(summary.subscription?.plan_id || "free");
      setMode(config);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar los planes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function activate(plan) {
    if (!canManage) return;
    setBusyPlan(plan.id);
    setError("");
    setSuccess("");
    try {
      const isFree = Number(plan.price_monthly) <= 0;
      if (isFree) {
        await api("/api/billing/change-plan", {
          method: "POST",
          body: JSON.stringify({ plan_id: plan.id }),
        });
        setSuccess("Plan Free activado.");
      } else {
        const session = await api("/api/billing/checkout", {
          method: "POST",
          body: JSON.stringify({ plan_id: plan.id }),
        });
        if (session.provider === "mock") {
          await api("/api/billing/checkout/confirm", {
            method: "POST",
            body: JSON.stringify({ plan_id: plan.id }),
          });
          setSuccess("Pago de prueba confirmado. Tu plan ya está activo.");
        } else if (session.checkout_url) {
          window.location.href = session.checkout_url;
          return;
        }
      }
      await refreshBilling?.();
      await load();
    } catch (err) {
      setError(err.message || "No se pudo completar la compra.");
    } finally {
      setBusyPlan("");
    }
  }

  const activePlanName = billing?.subscription?.plan_name || plans.find((p) => p.id === currentPlanId)?.name || "Free";

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Planes y facturación</div>
          <h2>Elige el plan que se adapte a tu negocio</h2>
          <p>
            Desde ferreterías pequeñas hasta cadenas de distribución. Todos los planes incluyen
            auditoría de precios automatizada. Puedes cambiar de plan en cualquier momento.
          </p>
        </div>
        <span className="counter-chip">Plan actual: {activePlanName}</span>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      {mode.test_mode ? (
        <div className="alert warning">
          <ShieldIcon />
          <span>
            Modo test: los pagos se simulan y el plan se activa al confirmar, sin cobro real. Para
            cobrar de verdad, configura STRIPE/MERCADOPAGO/FLOW y PAYMENT_PROVIDER en el servidor.
          </span>
        </div>
      ) : (
        <div className="alert success">
          <ShieldIcon />
          <span>
            Pagos reales vía {mode.provider}. Serás redirigido a la pasarela y el plan se activa
            automáticamente cuando el pago se confirme.
          </span>
        </div>
      )}

      {!canManage ? (
        <div className="alert warning">
          <span>Solo el propietario o un administrador pueden cambiar el plan.</span>
        </div>
      ) : null}

      {loading ? (
        <div className="empty-state">Cargando planes…</div>
      ) : (
        <section className="pricing-section">
          <div className="pricing-grid">
            {plans.map((plan) => {
              const isCurrent = currentPlanId === plan.id;
              const popular = plan.id === "pro";
              const price = priceFor(plan);
              return (
                <div
                  key={plan.id}
                  className={`pricing-card ${popular ? "popular" : ""} ${isCurrent ? "current" : ""}`}
                >
                  <div className="pricing-header-card">
                    <h3>{plan.name}</h3>
                    {popular ? <span className="popular-badge">Más popular</span> : null}
                    {isCurrent ? <span className="current-badge">Tu plan actual</span> : null}
                  </div>
                  <div className="pricing-price">
                    <span className="price-amount">{price.amount}</span>
                    {price.period ? <span className="price-period">{price.period}</span> : null}
                  </div>
                  <p className="pricing-description">{plan.description}</p>

                  <div className="pricing-limits">
                    <span className="pricing-limit">
                      <UsersIcon /> {usersFor(plan)}
                    </span>
                    <span className="pricing-limit">
                      <DollarIcon /> {docsFor(plan)}
                    </span>
                  </div>

                  <ul className="pricing-features">
                    {(plan.features || []).map((feature) => (
                      <li key={feature} className="feature-item available">
                        <span className="feature-check yes">
                          <CheckIcon />
                        </span>
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <div className="pricing-cta">
                    {isCurrent ? (
                      <button type="button" className="button ghost" disabled>
                        Plan actual
                      </button>
                    ) : (
                      <button
                        type="button"
                        className={`button ${popular ? "primary" : "ghost"}`}
                        onClick={() => activate(plan)}
                        disabled={!canManage || busyPlan === plan.id}
                      >
                        {busyPlan === plan.id
                          ? "Procesando…"
                          : Number(plan.price_monthly) <= 0
                            ? "Cambiar a Free"
                            : `Contratar ${plan.name}`}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pricing-faq">
            <h3>Preguntas frecuentes</h3>
            <div className="faq-item">
              <h4>¿Puedo cambiar de plan en cualquier momento?</h4>
              <p>
                Sí. Los planes pagados se activan al confirmar el pago y puedes volver al plan Free
                cuando quieras.
              </p>
            </div>
            <div className="faq-item">
              <h4>¿Qué pasa si supero mi límite de usuarios o documentos?</h4>
              <p>
                El límite de usuarios incluye miembros activos e invitaciones pendientes. Si llegas
                al cupo, actualiza tu plan para invitar a más personas o procesar más documentos.
              </p>
            </div>
            <div className="faq-item">
              <h4>¿Cómo se confirma mi pago?</h4>
              <p>
                En producción la pasarela confirma el pago automáticamente mediante webhook firmado.
                En modo test el pago se simula para que puedas validar el flujo completo.
              </p>
            </div>
            <div className="faq-item">
              <h4>¿Incluye soporte?</h4>
              <p>
                Todos los planes incluyen soporte por email. Los planes Pro y Enterprise incluyen
                soporte prioritario con tiempos de respuesta más rápidos.
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
