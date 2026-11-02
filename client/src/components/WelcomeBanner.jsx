import { useEffect, useState } from "react";
import { CheckIcon, SparkIcon } from "./Icons";
import { useAuth } from "../context/AuthContext";

const STEPS = [
  {
    id: 1,
    icon: "📄",
    title: "Entrada",
    description: "Arrastra y suelta tu factura PDF o Excel de proveedores.",
  },
  {
    id: 2,
    icon: "⚡",
    title: "Procesamiento IA",
    description:
      "Normalización automática de SKUs y cruce de precios unitarios en tiempo real.",
  },
  {
    id: 3,
    icon: "💰",
    title: "Resultado / Ahorro",
    description:
      "Alerta inmediata de alzas y ahorro estimado antes de pagar la factura.",
  },
];

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "US$ 0",
    limit: "25 documentos / mes",
    features: ["Auditoría básica", "Dashboard mensual"],
    popular: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: "US$ 49",
    limit: "500 documentos / mes",
    features: [
      "Equipo con roles",
      "Alertas de cuota",
      "Exportaciones PDF y Excel",
      "Historial de 6 meses",
    ],
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "US$ 199",
    limit: "Documentos ilimitados",
    features: [
      "Panel multi-tenant",
      "Auditoría avanzada",
      "Exportaciones masivas",
      "Gestión centralizada",
    ],
    popular: false,
  },
];

export default function WelcomeBanner() {
  const { organization } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [progress, setProgress] = useState(0);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!demoOpen) return undefined;
    setProgress(0);
    const id = setInterval(() => {
      setProgress((current) => {
        if (current >= 100) {
          clearInterval(id);
          return 100;
        }
        return current + 5;
      });
    }, 250);
    return () => clearInterval(id);
  }, [demoOpen]);

  useEffect(() => {
    if (!notice) return undefined;
    const id = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(id);
  }, [notice]);

  const name = organization?.name ? `, ${organization.name}` : "";

  return (
    <section className="welcome">
      <div className="welcome-hero">
        <div className="welcome-copy">
          <span className="welcome-badge">
            <SparkIcon />
            Auditoría continua v2.0
          </span>

          <h1>Bienvenido/a a NEXORA{name}</h1>

          <p className="welcome-lead">
            Evita pagar de más en facturas y cotizaciones. Nuestra IA detecta alzas de precios
            ocultas y normaliza SKUs en CLP automáticamente antes de que pagues.
          </p>

          <div className="welcome-actions">
            <button
              type="button"
              className="button primary"
              onClick={() => setNotice("Abre la sección Documentos para cargar tu primera factura.")}
            >
              Cargar documento
            </button>
            <button type="button" className="button ghost" onClick={() => setDemoOpen(true)}>
              Ver tutorial interactivo
            </button>
          </div>

          {notice ? (
            <p className="welcome-notice" role="status">
              {notice}
            </p>
          ) : null}
        </div>

        <div className="welcome-journey">
          <h2>El viaje del ahorro</h2>
          <ol className="welcome-steps">
            {STEPS.map((step) => (
              <li key={step.id} className="welcome-step">
                <span className="welcome-step-icon" aria-hidden="true">
                  {step.icon}
                </span>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
          <button type="button" className="button ghost full" onClick={() => setDemoOpen(true)}>
            ▶ Ver demo flash
          </button>
        </div>
      </div>

      <div className="welcome-plans-head">
        <h2>Planes</h2>
        <p>Empieza gratis y escala cuando tu operación lo necesite.</p>
      </div>

      <div className="welcome-plans">
        {PLANS.map((plan) => (
          <article key={plan.id} className={`welcome-plan ${plan.popular ? "featured" : ""}`}>
            {plan.popular ? <span className="welcome-plan-flag">Más popular</span> : null}
            <h3>{plan.name}</h3>
            <div className="welcome-plan-price">
              {plan.price}
              <small>/ mes</small>
            </div>
            <p className="welcome-plan-limit">{plan.limit}</p>
            <ul>
              {plan.features.map((feature) => (
                <li key={feature}>
                  <CheckIcon />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="button full"
              onClick={() => setNotice(`Plan ${plan.name} seleccionado. Gestiónalo desde Facturación.`)}
            >
              Elegir {plan.name}
            </button>
          </article>
        ))}
      </div>

      {demoOpen ? (
        <div
          className="welcome-modal"
          role="dialog"
          aria-modal="true"
          aria-label="Demo flash de NEXORA"
          onClick={() => setDemoOpen(false)}
        >
          <div className="welcome-modal-card" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="welcome-modal-close"
              onClick={() => setDemoOpen(false)}
              aria-label="Cerrar"
            >
              ✕
            </button>
            <h3>Demo flash · NEXORA</h3>
            <p className="welcome-modal-sub">Simulador del flujo de auditoría continua</p>

            <div
              className="welcome-progress"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={progress}
            >
              <span style={{ width: `${progress}%` }} />
            </div>

            <ol className="welcome-steps welcome-steps-demo">
              {STEPS.map((step) => (
                <li key={step.id} className="welcome-step">
                  <span className="welcome-step-icon" aria-hidden="true">
                    {step.icon}
                  </span>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.description}</p>
                  </div>
                </li>
              ))}
            </ol>

            <button type="button" className="button primary full" onClick={() => setDemoOpen(false)}>
              Cerrar demo
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
