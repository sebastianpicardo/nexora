import { useCallback, useEffect, useRef, useState } from "react";
import { CheckIcon, SparkIcon } from "./Icons";
import { useAuth } from "../context/AuthContext";

const DEMO_STEP_MS = 3000;

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

export default function WelcomeBanner({ videoSrc = "/assets/demo-preview.mp4" }) {
  const { organization } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [videoFailed, setVideoFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const closeTimer = useRef(null);

  const requestClose = useCallback(() => {
    if (closing) return;
    setClosing(true);
    closeTimer.current = setTimeout(() => {
      setDemoOpen(false);
      setClosing(false);
    }, 220);
  }, [closing]);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  useEffect(() => {
    if (!demoOpen) return undefined;
    setActiveStep(0);
    setVideoFailed(false);
    const id = setInterval(() => {
      setActiveStep((current) => (current + 1) % STEPS.length);
    }, DEMO_STEP_MS);
    return () => clearInterval(id);
  }, [demoOpen]);

  useEffect(() => {
    if (!demoOpen) return undefined;
    const handleKey = (event) => {
      if (event.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", handleKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [demoOpen, requestClose]);

  useEffect(() => {
    if (!notice) return undefined;
    const id = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(id);
  }, [notice]);

  const name = organization?.name ? `, ${organization.name}` : "";
  const currentStep = STEPS[activeStep];

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
          className={`welcome-modal ${closing ? "is-closing" : ""}`}
          role="presentation"
          onClick={requestClose}
        >
          <div
            className="welcome-demo-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="nexora-demo-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="welcome-demo-close"
              onClick={requestClose}
              aria-label="Cerrar demo"
            >
              ✕
            </button>

            <div className="welcome-demo-media">
              {videoFailed ? (
                <div className="welcome-demo-fallback">
                  <span className="welcome-demo-fallback-icon" aria-hidden="true">
                    {currentStep.icon}
                  </span>
                  <p>
                    Vista previa no disponible. Agrega <code>{videoSrc}</code> para ver la demo en
                    video.
                  </p>
                </div>
              ) : (
                <video
                  className="welcome-demo-video"
                  src={videoSrc}
                  autoPlay
                  loop
                  muted
                  playsInline
                  preload="metadata"
                  onError={() => setVideoFailed(true)}
                  aria-label="Demostración visual de NEXORA"
                />
              )}

              <div className="welcome-demo-overlay">
                <span className="welcome-demo-live">
                  <i />
                  Demo en vivo
                </span>
                <span className="welcome-demo-counter">
                  Paso {activeStep + 1} de {STEPS.length}
                </span>
              </div>
            </div>

            <div className="welcome-demo-body">
              <h3 id="nexora-demo-title">Demo flash · NEXORA</h3>
              <p className="welcome-demo-sub">
                El flujo de auditoría se reproduce automáticamente cada {DEMO_STEP_MS / 1000}{" "}
                segundos.
              </p>

              <div
                className="welcome-demo-progress"
                role="progressbar"
                aria-label="Progreso de la demo"
                aria-valuemin={1}
                aria-valuemax={STEPS.length}
                aria-valuenow={activeStep + 1}
              >
                {STEPS.map((step, index) => (
                  <span
                    key={step.id}
                    className={`welcome-demo-segment ${index <= activeStep ? "filled" : ""} ${
                      index === activeStep ? "current" : ""
                    }`}
                  />
                ))}
              </div>

              <ol className="welcome-demo-steps">
                {STEPS.map((step, index) => {
                  const state =
                    index === activeStep ? "active" : index < activeStep ? "done" : "pending";
                  return (
                    <li
                      key={step.id}
                      className={`welcome-demo-step ${state}`}
                      aria-current={index === activeStep ? "step" : undefined}
                    >
                      <span className="welcome-demo-step-icon" aria-hidden="true">
                        {step.icon}
                      </span>
                      <div>
                        <strong>{step.title}</strong>
                        <p>{step.description}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>

              <div className="welcome-demo-actions">
                <button type="button" className="button ghost" onClick={requestClose}>
                  Saltar introducción
                </button>
                <button type="button" className="button primary" onClick={requestClose}>
                  Cerrar demo
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
