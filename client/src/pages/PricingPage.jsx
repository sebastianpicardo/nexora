import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import {
  CheckIcon,
  DollarIcon,
  SparkIcon,
  ShieldIcon,
  UsersIcon,
  RocketIcon,
  CrownIcon,
  ArrowRightIcon,
} from "../components/Icons";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: 0,
    priceLabel: "Gratis",
    description: "Para comenzar a auditar tus compras",
    popular: false,
    features: [
      { label: "Hasta 50 documentos por mes", available: true },
      { label: "Auditoría automática de precios", available: true },
      { label: "Detección de excepciones", available: true },
      { label: "Aprobaciones de compra", available: true },
      { label: "Proveedores ilimitados", available: true },
      { label: "Exportación a Excel/PDF", available: false },
      { label: "Integración con ChileCompra / SII", available: false },
      { label: "Alertas proactivas (email/Slack)", available: false },
      { label: "API pública y webhooks", available: false },
      { label: "SSO con Google Workspace", available: false },
      { label: "White-label (marca blanca)", available: false },
      { label: "Soporte prioritario", available: false },
    ],
    cta: "Empezar gratis",
    color: "#10b981",
  },
  {
    id: "pro",
    name: "Pro",
    price: 49,
    priceLabel: "USD/mes",
    description: "Para equipos en crecimiento",
    popular: true,
    features: [
      { label: "Hasta 500 documentos por mes", available: true },
      { label: "Auditoría automática de precios", available: true },
      { label: "Detección de excepciones", available: true },
      { label: "Aprobaciones de compra", available: true },
      { label: "Proveedores ilimitados", available: true },
      { label: "Exportación a Excel/PDF", available: true },
      { label: "Integración con ChileCompra / SII", available: true },
      { label: "Alertas proactivas (email/Slack)", available: true },
      { label: "API pública y webhooks", available: true },
      { label: "SSO con Google Workspace", available: false },
      { label: "White-label (marca blanca)", available: false },
      { label: "Soporte prioritario", available: false },
    ],
    cta: "Empezar Pro",
    color: "#2563eb",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 149,
    priceLabel: "USD/mes",
    description: "Para distribuidores y cadenas",
    popular: false,
    features: [
      { label: "Documentos ilimitados", available: true },
      { label: "Auditoría automática de precios", available: true },
      { label: "Detección de excepciones", available: true },
      { label: "Aprobaciones de compra", available: true },
      { label: "Proveedores ilimitados", available: true },
      { label: "Exportación a Excel/PDF", available: true },
      { label: "Integración con ChileCompra / SII", available: true },
      { label: "Alertas proactivas (email/Slack)", available: true },
      { label: "API pública y webhooks", available: true },
      { label: "SSO con Google Workspace", available: true },
      { label: "White-label (marca blanca)", available: true },
      { label: "Soporte prioritario", available: true },
      { label: "Múltiples sucursales", available: true },
      { label: "Backup automático de BD", available: true },
    ],
    cta: "Contactar ventas",
    color: "#7c3aed",
  },
];

export default function PricingPage() {
  const { user, organization, billing, canManage } = useAuth();
  const [selectedPlan, setSelectedPlan] = useState("pro");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api("/api/billing/summary");
        if (!cancelled) {
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const currentPlan = billing?.subscription?.plan_name || "free";

  const handleSelect = (planId) => {
    setSelectedPlan(planId);
  };

  const handleUpgrade = (planId) => {
    if (!canManage) return;
    // Redirigir a la página de facturación o crear sesión de pago
    window.open(`/billing?plan=${planId}`, "_blank");
  };

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
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {loading ? (
        <div className="empty-state">Cargando planes…</div>
      ) : (
        <section className="pricing-section">
          <div className="pricing-header">
            <h2>Planes de precios</h2>
            <p>Elige el plan que mejor se adapte al tamaño de tu negocio.</p>
          </div>

          <div className="pricing-grid">
            {PLANS.map((plan) => {
              const isCurrent = currentPlan === plan.id;
              const isSelected = selectedPlan === plan.id;
              return (
                <div
                  key={plan.id}
                  className={`pricing-card ${plan.popular ? "popular" : ""} ${isCurrent ? "current" : ""} ${isSelected ? "selected" : ""}`}
                >
                  <div className="pricing-header-card">
                    <h3>{plan.name}</h3>
                    {plan.popular && (
                      <span className="popular-badge">Más popular</span>
                    )}
                    {isCurrent && (
                      <span className="current-badge">Tu plan actual</span>
                    )}
                  </div>
                  <div className="pricing-price">
                    <span className="price-currency">{plan.priceLabel}</span>
                    <span className="price-amount">${plan.price}</span>
                    <span className="price-period">/mes</span>
                  </div>
                  <p className="pricing-description">{plan.description}</p>
                  <ul className="pricing-features">
                    {plan.features.map((feature) => (
                      <li key={feature.label} className={`feature-item ${feature.available ? "available" : "unavailable"}`}>
                        <span className={`feature-check ${feature.available ? "yes" : "no"}`}>
                          {feature.available ? <CheckIcon /> : <span>✕</span>}
                        </span>
                        {feature.label}
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
                        className={`button ${plan.popular ? "primary" : "ghost"}`}
                        onClick={() => handleUpgrade(plan.id)}
                      >
                        {plan.cta}
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
              <p>Sí. Puedes actualizar o reducir tu plan desde la sección de Facturación. Los cambios se aplican de inmediato.</p>
            </div>
            <div className="faq-item">
              <h4>¿Qué pasa si supero mi límite de documentos?</h4>
              <p>Recibirás una notificación y podrás actualizar tu plan o esperar al próximo ciclo de facturación.</p>
            </div>
            <div className="faq-item">
              <h4>¿Incluye soporte?</h4>
              <p>Todos los planes incluyen soporte por email. Los planes Pro y Enterprise incluyen soporte prioritario con tiempo de respuesta más rápido.</p>
            </div>
            <div className="faq-item">
              <h4>¿Puedo probar el plan Pro antes de pagar?</h4>
              <p>Sí, tienes una prueba gratuita de 14 días. No se requiere tarjeta de crédito para comenzar.</p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
