import React from "react";
import { SparkIcon } from "../components/Icons";
import { useAuth } from "../context/AuthContext";

const heroGradient =
  "linear-gradient(135deg, #1e3a5f 0%, #2c5aa0 25%, #1e3a5f 50%, #2c5aa0 75%, #1e3a5f 100%)";

export default function WelcomeBanner({ autoPlay = true }) {
  const { organization, billing } = useAuth();

  const tutorialSteps = [
    {
      title: "Paso 1 – Subida",
      description:
        "Arrastra y suelta tu factura, cotización o lista de precios (PDF, Excel).",
    },
    {
      title: "Paso 2 – Normalización",
      description:
        "El motor IA automatiza la extracción, normaliza SKUs y precios unitarios en CLP.",
    },
    {
      title: "Paso 3 – Alertas",
      description:
        "Se detectan alzas de precio y se te notifica antes de pagar la factura.",
    },
  ];

  const planCards = [
    {
      id: "free",
      name: "Free",
      price: "US$ 0 /mes",
      limit: "25 documentos/mes",
      features: ["25 docs/mes", "Auditoría básica", "Dashboard mensual"],
    },
    {
      id: "pro",
      name: "Pro",
      price: "US$ 49 /mes",
      limit: "500 documentos/mes",
      features: [
        "500 docs/mes",
        "Equipo con roles",
        "Alertas de cuota",
        "Exportaciones PDF y Excel",
        "Historial 6 meses",
      ],
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: "US$ 199 /mes",
      limit: "Ilimitado",
      features: [
        "Documentos ilimitados",
        "Panel multi‑tenant",
        "Auditoría avanzada",
        "Exportaciones masivas",
        "Gestión centralizada",
      ],
    },
  ];

  const goToDocuments = () => {
    window.location.href = "/documents";
  };

  return (
    <section
      className="welcome-banner page-hero"
      style={{
        background: heroGradient,
        animation: "gradientShift 8s ease infinite",
      }}
    >
      <div className="hero-copy">
        <div className="eyebrow"><SparkIcon /> Auditoría continua</div>
        <h2>Bienvenido/a a NEXORA</h2>
        <p>
          NEXORA es una auditoría continua de compras e inteligencia de precios
          diseñada para ferreterías y distribuidoras industriales. Nuestra
          plataforma detecta automáticamente alzas de precios, normaliza SKUs y
          te ayuda a ahorrar dinero antes de pagar tus facturas.
        </p>
      </div>

      <div className="video-flash">
        <div className="video-flash-header">
          <span>▶ Tutorial rápido</span>
        </div>

        <p>
          <strong>3 pasos para una auditoría automática</strong>
        </p>
        {tutorialSteps.map((s, i) => (
          <p key={i}>
            <strong>{s.title}</strong>: {s.description}
          </p>
        ))}
      </div>

      <div className="plan-cards-grid">
        {planCards.map((p) => (
          <div
            key={p.id}
            style={{
              background: "rgba(255,255,255,0.07)",
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-sm)",
              padding: "20px",
              textAlign: "center",
              transition: "transform 0.2s",
              marginBottom: "12px",
              cursor: "pointer",
            }}
            onClick={() => goToDocuments()}
          >
            <strong>{p.name}</strong><br />
            {p.price}<br />
            {p.limit}<br />
            <small>{p.features.join(", ")}</small>
          </div>
        ))}
      </div>
    </section>
  );
}