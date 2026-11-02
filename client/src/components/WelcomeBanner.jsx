/* ------------------------------------------------------------------
   WelcomeBanner – Demo Flash (video‑free, simulator‑only)
   ------------------------------------------------------------------ */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AnimatePresence,
  motion,
  useReducedMotion,
} from "framer-motion";

import { CheckIcon, SparkIcon } from "./Icons";
import { useAuth } from "../context/AuthContext";

/* ------------------------------------------------------------------
   Pasos de la demo (texto 100 % en español)
   ------------------------------------------------------------------ */
const DEMO_STEP_MS = 3000;

const STEPS = [
  {
    id: 1,
    icon: "📄",
    title: "Entrada",
    description:
      "Arrastra y suelta tu factura PDF o Excel de proveedores.",
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

/* ------------------------------------------------------------------
   Sub‑componentes animados del simulador (panel izquierdo)
   ------------------------------------------------------------------ */

/* ── Paso 1 – arrastre de documento ───────────────────────────────── */
const Step1 = () => {
  const [dragging, setDragging] = useState(false);
  const onDragStart = () => setDragging(true);
  const onDragEnd = () => setDragging(false);

  return (
    <motion.div
      className="doc-box"
      drag={onDragStart}
      dragEnd={onDragEnd}
      whileDrag={{ opacity: 0.7 }}
      style={{
        width: 80,
        height: 44,
        background: "#e2e8f0",
        borderRadius: 6,
        margin: "auto",
        display: "grid",
        placeItems: "center",
        color: "#4a5568",
        fontSize: 12,
        transition: "opacity 0.2s ease",
      }}
    >
      📄{" "}
      <span className="sr-only">Documento</span>
    </motion.div>
  );
};

/* ── Paso 2 – “escaneo” de IA ─────────────────────────────────────── */
const Step2 = () => {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className="ai-loader"
      initial={{ rotate: 0, opacity: 0.6 }}
      animate={{ rotate: 360 }}
      transition={{
        duration: reduce ? 0 : 5,
        repeat: Infinity,
        ease: "linear",
      }}
    >
      <svg
        width={40}
        height={40}
        viewBox="0 0 24 24"
        style={{ fill: "#38bdf8" }}
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="10" y1="10" x2="14" y2="14" stroke="white" stroke-width="2" />
      </svg>
    </motion.div>
  );
};

/* ── Paso 3 – tarjeta flotante de ahorro ───────────────────────────── */
const Step3 = () => {
  return (
    <motion.div
      className="floating-card"
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -20, opacity: 0 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 30,
      }}
    >
      <div className="card-body">
        <h4 className="title">✅ Factura procesada</h4>
        <p className="saved">
          <strong>Ahorro estimado:</strong> $ 124.50
          <span className="alert">· Alerta: precio ↑ 3 % vs histórico</span>
        </p>
        <button className="btn-close" aria-label="Cerrar">
          ✕
        </button>
      </div>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Panel simulador – muestra el contenido correspondiente al paso activo
   ------------------------------------------------------------------ */
const SimulatorPanel = ({ activeStep }) => {
  const reduce = useReducedMotion();
  const motionSafe = !reduce;

  const panelContent = {
    1: (
      <motion.section
        key="step1"
        className="step-panel"
        initial={{ x: 20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: -20, opacity: 0 }}
        transition={{ duration: motionSafe ? 0.4 : 0, type: "spring" }}
      >
        <h5 className="step-title">Paso 1 – Entrada</h5>
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
        <h5 className="step-title">Paso 2 – Procesamiento IA</h5>
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
        <h5 className="step-title">Paso 3 – Resultado / Ahorro</h5>
        <Step3 />
        <p className="step-sub">
          Se genera un informe con el ahorro estimado y alertas de variación
          de precios.
        </p>
      </motion.section>
    ),
  };

  return <>{panelContent[activeStep] ?? null}</>;
};

/* ------------------------------------------------------------------
   Componente principal – WelcomeBanner
   ------------------------------------------------------------------ */
export default function WelcomeBanner() {
  const { organization } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [notice, setNotice] = useState("");

  /* ----- Auto‑avance cada 3 s ----- */
  useEffect(() => {
    if (!demoOpen) return undefined;
    const id = setInterval(() =>
      setActiveStep((cur) => (cur + 1) % STEPS.length),
    );
    return () => clearInterval(id);
  }, [demoOpen]);

  /* ----- Focus / scroll‑lock (igual que antes) ----- */
  useEffect(() => {
    if (!demoOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKey = (e) => {
      if (e.key === "Escape") setDemoOpen(false);
    };
    document.addEventListener("keydown", handleKey);

    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [demoOpen]);

  /* ----- Notificaciones breves ----- */
  useEffect(() => {
    if (!notice) return undefined;
    const tid = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(tid);
  }, [notice]);

  const name = organization?.name ? `, ${organization.name}` : "";

  return (
    <section className="welcome">
      {/* ---------------------- Zona superior (sin cambios) ---------------------- */
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
            <button
              type="button"
              className="button ghost"
              onClick={() => setDemoOpen(true)}
            >
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

      {/* ---------------------- Panel izquierdo: simulador ---------------------- */}
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
              className="welcome-demo-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="nexora-demo-title"
              onClick={(e) => e.stopPropagation()}
            >
              {/* -------- Close (✕) -------- */}
              <button
                type="button"
                className="welcome-demo-close"
                onClick={() => setDemoOpen(false)}
                aria-label="Cerrar demo"
              >
                ✕
              </button>

              {/* ---------- Panel izquierdo: simulador animado ---------------- */}
              <div className="welcome-demo-media">
                <SimulatorPanel activeStep={activeStep} />

                {/* Barra de progreso superior (siempre visible) */}
                <div
                  className="welcome-demo-media-progress"
                  aria-hidden="true"
                >
                  <motion.span
                    initial={false}
                    animate={{
                      width: `${((activeStep + 1) / STEPS.length) * 100}%`,
                    }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.55,
                      ease: "easeInOut",
                    }}
                  />
                </div>

                {/* Overlay con contador y modo “en vivo” (idéntico al anterior) */}
                <div className="welcome-demo-overlay">
                  <span className="welcome-demo-live">
                    <i /> Demo en vivo
                  </span>
                  <span className="welcome-demo-counter">
                    Paso {activeStep + 1} de {STEPS.length}
                  </span>
                </div>
              </div>

              {/* ---------- Cuerpo derecho: progreso + pasos (idéntico) -------- */}
              <div className="welcome-demo-body">
                <h3 id="nexora-demo-title">Demostración Flash · NEXORA</h3>
                <p className="welcome-demo-sub">
                  El flujo de auditoría se reproduce automáticamente cada
                  {DEMO_STEP_MS / 1000} segundos.
                </p>

                <p
                  className="sr-only"
                  aria-live="polite"
                >
                  Paso {activeStep + 1} de {STEPS.length}: {STEPS[activeStep].title}
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
                      className={`welcome-demo-segment ${index <= activeStep
                        ? "filled"
                        : ""} ${
                            index === activeStep ? "current" : ""
                          }`}
                  />
                </div>)

                <ol className="welcome-demo-steps">
                  {STEPS.map((step, index) => {
                    const state =
                      index === activeStep ? "active" : index < activeStep
                        ? "done"
                        : "pending";
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
                  <button
                    type="button"
                    className="button ghost"
                    onClick={setDemoOpen false}>Saltar introducción</button>
                  <button
                    type="button"
                    className="button primary"
                    onClick={setDemoOpen false}>Cerrar demo</button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}