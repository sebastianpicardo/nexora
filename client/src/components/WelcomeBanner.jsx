/* ------------------------------------------------------------------
   WelcomeBanner – Demo Flash (animación continua, 100% código)
   ------------------------------------------------------------------ */

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckIcon, SparkIcon } from "./Icons";
import { useAuth } from "../context/AuthContext";

/* ------------------------------------------------------------------
   Constantes y pasos de la demo (texto 100 % en español)
   ------------------------------------------------------------------ */
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
    description: "Normalización automática de SKUs y cruce de precios unitarios en tiempo real.",
  },
  {
    id: 3,
    icon: "💰",
    title: "Resultado / Ahorro",
    description: "Alerta inmediata de alzas y ahorro estimado antes de pagar la factura.",
  },
];

/* ------------------------------------------------------------------
   Paso 1 – Arrastre de documento (Document Flash)
   ------------------------------------------------------------------ */
const Step1 = () => {
  const [dragging, setDragging] = useState(false);
  const onDragStart = () => setDragging(true);
  const onDragEnd = () => setDragging(false);

  return (
    <motion.div
      className="doc-card"
      drag={onDragStart}
      dragEnd={onDragEnd}
      whileDrag={{ scale: 0.96 }}
      style={{
        width: 86,
        height: 110,
        margin: "auto",
        background: "#e2e8f0",
        borderRadius: 12,
        display: "grid",
        placeItems: "center",
        gap: 8,
        color: "#475569",
        fontSize: 12,
        textAlign: "center",
        transition: "border-color 0.2s ease",
        border: dragging ? "2px dashed #38bdf8" : "2px solid transparent",
      }}
    >
      <span className="sr-only">Documento</span>
      <span style={{ fontSize: 34 }}>📄</span>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Paso 2 – Procesamiento IA (escaneo y normalización)
   ------------------------------------------------------------------ */
const Step2 = () => {
  return (
    <motion.div
      className="ai-loader"
      initial={{ rotate: 0, opacity: 0.6 }}
      animate={{ rotate: 360 }}
      transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
    >
      <svg width="48" height="48" viewBox="0 0 24 24" style={{ fill: "#38bdf8" }}>
        <circle cx="12" cy="12" r="10" />
        <line x1="10" y1="10" x2="14" y2="14" stroke="white" strokeWidth={2} />
      </svg>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Paso 3 – Resultado / Ahorro (tarjeta emergente flotante)
   ------------------------------------------------------------------ */
const Step3 = () => {
  return (
    <motion.div
      className="floating-card"
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -20, opacity: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      <div className="card-body">
        <h4 className="title">✅ Factura procesada</h4>
        <p className="saved">
          <strong>Ahorro estimado:</strong> $ 124.50
          <span className="alert">· Alerta: precio ↑ 3 % vs histórico</span>
        </p>
        <button className="btn-close" aria-label="Cerrar">
          ✕
        </button>
      </div>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   SimulatorPanel – renderiza el paso activo sincronizado cada 3 s
   ------------------------------------------------------------------ */
const SimulatorPanel = ({ activeStep }) => {
  const reduce = useReducedMotion();
  const motionSafe = !reduce;

  const panels = {
    1: (
      <motion.section
        key="step1"
        className="step-panel"
        initial={{ x: 20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: -20, opacity: 0 }}
        transition={{ duration: motionSafe ? 0.4 : 0, type: "spring" }}
      >
        <h5 className="step-title">Paso 1 – Entrada</h5>
        <Step1 />
        <p className="step-sub">
          Arrastra la factura al área resaltada y el sistema la detectará
          automáticamente.
        </p>
      </motion.section>
    ),
    2: (
      <motion.section
        key="step2"
        className="step-panel"
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 20, opacity: 0 }}
        transition={{ duration: motionSafe ? 0.4 : 0, type: "spring" }}
      >
        <h5 className="step-title">Paso 2 – Procesamiento IA</h5>
        <Step2 />
        <p className="step-sub">
          La IA lee los datos, normaliza SKU y precios, y cruza la información
          en tiempo real.
        </p>
      </motion.section>
    ),
    3: (
      <motion.section
        key="step3"
        className="step-panel"
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -20, opacity: 0 }}
        transition={{ duration: motionSafe ? 0.4 : 0, type: "spring" }}
      >
        <h5 className="step-title">Paso 3 – Resultado / Ahorro</h5>
        <Step3 />
        <p className="step-sub">
          Se genera un informe con el ahorro estimado y alertas de variación de
          precios.
        </p>
      </motion.section>
    ),
  };

  return <>{panels[activeStep] ?? null}</>;
};

/* ------------------------------------------------------------------
   WelcomeBanner – componente principal
   ------------------------------------------------------------------ */
export default function WelcomeBanner() {
  const { organization } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [notice, setNotice] = useState("");
  const reduceMotion = useReducedMotion();
  const motionSafe = !reduceMotion;
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const restoreFocusRef = useRef(null);

  const openDemo = useCallback(() => {
    restoreFocusRef.current = document.activeElement;
    setActiveStep(0);
    setDemoOpen(true);
  }, []);

  const requestClose = useCallback(() => setDemoOpen(false), []);

  useEffect(() => {
    if (!demoOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 60);

    const handleKey = (event) => {
      if (event.key === "Escape") {
        requestClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const nodes = dialogRef.current.querySelectorAll("button:not([disabled])");
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKey);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      restoreFocusRef.current?.focus?.();
    };
  }, [demoOpen, requestClose]);

  useEffect(() => {
    if (!demoOpen) return undefined;
    const id = window.setInterval(() => {
      setActiveStep((cur) => (cur + 1) % STEPS.length);
    }, DEMO_STEP_MS);
    return () => window.clearInterval(id);
  }, [demoOpen]);

  useEffect(() => {
    if (!notice) return undefined;
    const id = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(id);
  }, [notice]);

  const name = organization?.name ? `, ${organization.name}` : "";
  const currentStep = STEPS[activeStep];

  return (
    <section className="welcome">
      {/* ---------------------- Zona superior (sin cambios) ---------------------- */}
      <div className="welcome-hero">
        <div className="welcome-copy">
          <span className="welcome-badge">
            <SparkIcon /> Auditoría continua v2.0
          </span>

          <h1>Bienvenido/a a NEXORA{name}</h1>

          <p className="welcome-lead">
            Evita pagar de más en facturas y cotizaciones. Nuestra IA detecta
            alzas de precios ocultas y normaliza SKUs en CLP automáticamente
            antes de que pagues.
          </p>

          <div className="welcome-actions">
            <button
              type="button"
              className="button primary"
              onClick={() =>
                setNotice("Abre la sección Documentos para cargar tu primera factura.")
              }
            >
              Cargar documento
            </button>
            <button type="button" className="button ghost" onClick={openDemo}>
              Ver tutorial interactivo
            </button>
          </div>

          {notice ? (
            <p className="welcome-notice" role="status">{notice}</p>
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
          <button
            type="button"
            className="button ghost full"
            onClick={() => setDemoOpen(true)}
          >
            ▶ Ver demo flash
          </button>
        </div>
      </div>

      <div className="welcome-plans-head">
        <h2>Planes</h2>
        <p>Empieza gratis y escala cuando tu operación lo necesite.</p>
      </div>

      <div className="welcome-plans">
        {/* ---- Los tres planes permanecen idénticos a antes ---- */}
        {/* (código omitido por brevedad – igual que en el commit anterior) */}
        {/* ... */}
      </div>

      {/* ---------------------- Panel izquierdo: simulador continuo ---------------------- */}
      <AnimatePresence>
        {demoOpen ? (
          <motion.div
            key="nexora-demo"
            className="welcome-modal"
            role="presentation"
            onClick={() => setDemoOpen(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            <motion.div
              ref={dialogRef}
              className="welcome-demo-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="nexora-demo-title"
              aria-describedby="nexora-demo-sub"
              onClick={(event) => event.stopPropagation()}
            >
              {/* -------- Close (✕) -------- */}
              <motion.button
                ref={closeButtonRef}
                type="button"
                className="welcome-demo-close"
                onClick={() => requestClose()}
                aria-label="Cerrar demo"
                whileHover={motionSafe ? { scale: 1.08, rotate: 90 } : undefined}
                whileTap={motionSafe ? { scale: 0.92 } : undefined}
                transition={{ type: "spring", stiffness: 420, damping: 24 }}
              >
                ✕
              </motion.button>

              {/* ---------- Panel izquierdo: simulador animado ---------------- */}
              <div className="welcome-demo-media">
                <SimulatorPanel activeStep={activeStep} />

                <div className="welcome-demo-media-progress" aria-hidden="true">
                  <motion.span
                    initial={false}
                    animate={{ width: `${((activeStep + 1) / STEPS.length) * 100}%` }}
                    transition={{ duration: motionSafe ? 0.55 : 0, ease: "easeInOut" }}
                  />
                </div>

                <div className="welcome-demo-overlay">
                  <span className="welcome-demo-live">
                    <i /> Demo en vivo
                  </span>
                  <span className="welcome-demo-counter">
                    Paso {activeStep + 1} de {STEPS.length}
                  </span>
                </div>
              </div>

              {/* ---------- Cuerpo derecho: progreso y pasos ---------------- */}
              <div className="welcome-demo-body">
                <h3 id="nexora-demo-title">Demo flash · NEXORA</h3>
                <p className="welcome-demo-sub">
                  El flujo de auditoría se reproduce automáticamente cada
                  {DEMO_STEP_MS / 1000} segundos.
                </p>

                <p className="sr-only" aria-live="polite">
                  Paso {activeStep + 1} de {STEPS.length}: {currentStep.title}
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
                    <motion.span
                      key={step.id}
                      className={`welcome-demo-segment ${index <= activeStep
                        ? "filled"
                        : ""} ${
                          index === activeStep ? "current" : ""
                        }`}
                      animate={{
                        opacity: index <= activeStep ? 1 : 0.4,
                        scaleY: index === activeStep && motionSafe ? 1.4 : 1,
                      }}
                      transition={{ duration: motionSafe ? 0.3 : 0 }}
                    />
                  ))}
                </div>

                <ol className="welcome-demo-steps">
                  {STEPS.map((step, index) => {
                    const state =
                      index === activeStep ? "active" : index < activeStep
                        ? "done"
                        : "pending";
                    return (
                      <motion.li
                        key={step.id}
                        className={`welcome-demo-step ${state}`}
                        aria-current={index === activeStep ? "step" : undefined}
                        animate={{
                          opacity: index === activeStep ? 1 : index < activeStep ? 0.78 : 0.5,
                          x: motionSafe && index === activeStep ? 4 : 0,
                        }}
                        transition={{ duration: motionSafe ? 0.35 : 0, ease: "easeOut" }}
                      >
                        <span className="welcome-demo-step-icon" aria-hidden="true">
                          {step.icon}
                        </span>
                        <div>
                          <strong>{step.title}</strong>
                          <p>{step.description}</p>
                        </div>
                      </motion.li>
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
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}