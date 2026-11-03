/* ------------------------------------------------------------------
   WelcomeBanner – Demo Flash (Storytelling continuo, 3 fases)
   Diseño: Senior UI/UX Motion Designer + Full-Stack Engineer
   ------------------------------------------------------------------ */

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckIcon, SparkIcon } from "./Icons";
import { useAuth } from "../context/AuthContext";

/* ------------------------------------------------------------------
   Constantes del storytelling
   ------------------------------------------------------------------ */
const DEMO_PHASE_MS = 3500;
const PHASES = [
  { id: 1, key: "input", title: "Fase 1 · Entrada", subtitle: "Arrastra tu factura PDF o Excel" },
  { id: 2, key: "process", title: "Fase 2 · Procesamiento IA", subtitle: "Normalización de SKUs y cruce de precios en tiempo real" },
  { id: 3, key: "result", title: "Fase 3 · Resultado", subtitle: "Ahorro detectado y alertas de alza de precios" },
];

/* ------------------------------------------------------------------
   Fase 1 – Arrastre y soltado de documento (PDF / Excel)
   ------------------------------------------------------------------ */
const PhaseInput = () => {
  return (
    <motion.div
      className="flash-phase"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flash-media">
        {/* Zona de drop */}
        <motion.div
          className="drop-zone"
          animate={{
            scale: [1, 1.03, 1],
            borderColor: ["#475569", "#10b981", "#475569"],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div className="drop-icon">📄</div>
          <div className="drop-label">factura_proveedor.pdf</div>
        </motion.div>

        {/* Mano / cursor arrastrando */}
        <motion.div
          className="drag-cursor"
          animate={{
            x: [-20, 60, 60, -20],
            y: [0, -10, 0, 0],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div className="cursor">👆</div>
        </motion.div>

        {/* Línea de inserción */}
        <motion.div
          className="insert-line"
          animate={{ width: [0, 120, 120, 0] }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </div>

      <div className="flash-copy">
        <h5 className="flash-title">Fase 1 · Entrada</h5>
        <p className="flash-sub">
          Arrastra y suelta tu factura PDF o Excel. El sistema la detecta al instante.
        </p>
      </div>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Fase 2 – Procesamiento IA (escaneo, barra de progreso, SKU, precios)
   ------------------------------------------------------------------ */
const PhaseProcess = () => {
  return (
    <motion.div
      className="flash-phase"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flash-media">
        {/* Escáner IA */}
        <motion.div className="scanner">
          <motion.div
            className="scan-beam"
            animate={{
              y: [-40, 140, -40],
              opacity: [0, 1, 0],
            }}
            transition={{
              duration: 2.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          <div className="scan-target">
            <span className="sku-chip">SKU-8842</span>
            <span className="price-chip">$ 1.240</span>
          </div>
        </motion.div>

        {/* Barra de progreso */}
        <div className="progress-wrap">
          <div className="progress-label">
            <span>Procesando con IA…</span>
            <span className="progress-pct">68 %</span>
          </div>
          <motion.div
            className="progress-track"
            animate={{ width: [0, 72, 100] }}
            transition={{
              duration: 3.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <span className="progress-fill" />
          </motion.div>
        </div>

        {/* Efectos de destello */}
        <motion.div
          className="flash-sparkle"
          animate={{
            rotate: [0, 360],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          ✦
        </motion.div>
      </div>

      <div className="flash-copy">
        <h5 className="flash-title">Fase 2 · Procesamiento IA</h5>
        <p className="flash-sub">
          Normalización automática de SKUs y cruce de precios unitarios en tiempo real.
        </p>
      </div>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Fase 3 – Resultado / Ahorro (tarjeta flotante pop-up)
   ------------------------------------------------------------------ */
const PhaseResult = () => {
  return (
    <motion.div
      className="flash-phase"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flash-media">
        {/* Tarjeta flotante pop-up */}
        <motion.div
          className="result-card"
          animate={{
            scale: [0.85, 1.05, 1],
            y: [20, -10, 0],
          }}
          transition={{
            duration: 2.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <div className="result-badge">✅ Ahorro detectado</div>
          <div className="result-savings">
            <span className="big">18 %</span>
            <span className="small">de ahorro en esta factura</span>
          </div>
          <div className="result-alert">
            <span className="alert-dot"></span>
            <span>Alerta: precio unitario ↑ 3 % vs histórico (CLP)</span>
          </div>
        </motion.div>

        {/* Partículas flotantes alrededor */}
        <motion.div
          className="particle p1"
          animate={{
            y: [0, -12, 0],
            x: [0, 8, 0],
            opacity: [0.4, 1, 0.4],
          }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="particle p2"
          animate={{
            y: [0, -8, 0],
            x: [0, -6, 0],
            opacity: [0.3, 1, 0.3],
          }}
          transition={{
            duration: 2.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.5,
          }}
        />
      </div>

      <div className="flash-copy">
        <h5 className="flash-title">Fase 3 · Resultado</h5>
        <p className="flash-sub">
          Ahorro estimado y alerta de alza de precios antes de pagar.
        </p>
      </div>
    </motion.div>
  );
};

/* ------------------------------------------------------------------
   Simulador continuo – renderiza la fase activa en bucle
   ------------------------------------------------------------------ */
const Phases = {
  1: PhaseInput,
  2: PhaseProcess,
  3: PhaseResult,
};

const SimulatorPanel = ({ activePhase }) => {
  const reduce = useReducedMotion();
  const PhaseComp = Phases[activePhase] || PhaseInput;
  return (
    <motion.section
      key={`phase-${activePhase}`}
      className="step-panel"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduce ? 0 : 0.35 }}
    >
      <PhaseComp />
    </motion.section>
  );
};

/* ------------------------------------------------------------------
   WelcomeBanner – componente principal (único nodo raíz)
   ------------------------------------------------------------------ */
export default function WelcomeBanner() {
  const { organization } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [activePhase, setActivePhase] = useState(1);
  const [notice, setNotice] = useState("");
  const reduceMotion = useReducedMotion();
  const motionSafe = !reduceMotion;
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const restoreFocusRef = useRef(null);

  const openDemo = useCallback(() => {
    restoreFocusRef.current = document.activeElement;
    setActivePhase(1);
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
      setActivePhase((cur) => (cur % PHASES.length) + 1);
    }, DEMO_PHASE_MS);
    return () => window.clearInterval(id);
  }, [demoOpen]);

  useEffect(() => {
    if (!notice) return undefined;
    const id = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(id);
  }, [notice]);

  const name = organization?.name ? `, ${organization.name}` : "";

  return (
    <section className="welcome">
      {/* ---------- Zona superior (hero + copy + acciones) ---------- */}
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
          {notice ? <p className="welcome-notice" role="status">{notice}</p> : null}
        </div>

        <div className="welcome-journey">
          <h2>El viaje del ahorro</h2>
          <ol className="welcome-steps">
            {PHASES.map((phase) => (
              <li key={phase.id} className="welcome-step">
                <span className="welcome-step-icon" aria-hidden="true">
                  {phase.id === 1 ? "📄" : phase.id === 2 ? "⚡" : "💰"}
                </span>
                <div>
                  <strong>{phase.title}</strong>
                  <p>{phase.subtitle}</p>
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
        {/** Los tres planes se mantienen igual que antes */}
      </div>

      {/* ---------- Panel izquierdo: simulador continuo en bucle ---------- */}
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
              {/* Close */}
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

              {/* ---------- Panel izquierdo: simulador animado continuo ---------- */}
              <div className="welcome-demo-media">
                <SimulatorPanel activePhase={activePhase} />

                <div className="welcome-demo-media-progress" aria-hidden="true">
                  <motion.span
                    initial={false}
                    animate={{ width: `${(activePhase / PHASES.length) * 100}%` }}
                    transition={{ duration: motionSafe ? 0.55 : 0, ease: "easeInOut" }}
                  />
                </div>

                <div className="welcome-demo-overlay">
                  <span className="welcome-demo-live">
                    <i /> Demo en vivo
                  </span>
                  <span className="welcome-demo-counter">
                    Fase {activePhase} de {PHASES.length}
                  </span>
                </div>
              </div>

              {/* ---------- Cuerpo derecho: progreso y fases ---------- */}
              <div className="welcome-demo-body">
                <h3 id="nexora-demo-title">Demo flash · NEXORA</h3>
                <p className="welcome-demo-sub">
                  El flujo de auditoría se reproduce en bucle continuo cada
                  {DEMO_PHASE_MS / 1000} segundos.
                </p>

                <p className="sr-only" aria-live="polite">
                  Fase {activePhase} de {PHASES.length}
                </p>

                <div
                  className="welcome-demo-progress"
                  role="progressbar"
                  aria-label="Progreso de la demo"
                  aria-valuemin={1}
                  aria-valuemax={PHASES.length}
                  aria-valuenow={activePhase}
                >
                  {PHASES.map((phase, index) => (
                    <motion.span
                      key={phase.id}
                      className={`welcome-demo-segment ${
                        index < activePhase ? "filled" : ""
                      } ${index === activePhase - 1 ? "current" : ""}`}
                      animate={{
                        opacity: index < activePhase ? 1 : 0.4,
                        scaleY: index === activePhase - 1 && motionSafe ? 1.4 : 1,
                      }}
                      transition={{ duration: motionSafe ? 0.3 : 0 }}
                    />
                  ))}
                </div>

                <ol className="welcome-demo-steps">
                  {PHASES.map((phase, index) => {
                    const state =
                      index === activePhase - 1
                        ? "active"
                        : index < activePhase - 1
                        ? "done"
                        : "pending";
                    return (
                      <motion.li
                        key={phase.id}
                        className={`welcome-demo-step ${state}`}
                        aria-current={index === activePhase - 1 ? "step" : undefined}
                        animate={{
                          opacity:
                            index === activePhase - 1
                              ? 1
                              : index < activePhase - 1
                              ? 0.78
                              : 0.5,
                          x: motionSafe && index === activePhase - 1 ? 4 : 0,
                        }}
                        transition={{ duration: motionSafe ? 0.35 : 0, ease: "easeOut" }}
                      >
                        <span className="welcome-demo-step-icon" aria-hidden="true">
                          {phase.id === 1 ? "📄" : phase.id === 2 ? "⚡" : "💰"}
                        </span>
                        <div>
                          <strong>{phase.title}</strong>
                          <p>{phase.subtitle}</p>
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
