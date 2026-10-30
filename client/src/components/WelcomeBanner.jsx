import React, { useState } from "react";
import { SparkIcon } from "../components/Icons";
import { useAuth } from "../context/AuthContext";

export default function WelcomeBanner({ autoPlay = true }) {
  const { organization, billing } = useAuth();

  /* -------------------------------------------------
     Estado de interacciones
     ------------------------------------------------- */
  const [flashOpen, setFlashOpen] = useState(false);
  const [loadToast, setLoadToast] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);

  /* -------------------------------------------------
     Pasos del flujo de auditoría (3 etapas)
     ------------------------------------------------- */
  const steps = [
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
        "Alerta inmediata: ¡Alza detectada! Ahorro estimado de $145.000 CLP en esta factura antes de pagarla.",
    },
  ];

  /* -------------------------------------------------
     Datos: Tarjetas de planes (Free, Pro, Enterprise)
     ------------------------------------------------- */
  const plans = [
    {
      id: "free",
      name: "Free",
      price: "US$ 0 /mes",
      limit: "25 documentos/mes",
      features: ["Auditoría básica", "Dashboard mensual"],
      popular: false,
    },
    {
      id: "pro",
      name: "Pro",
      price: "US$ 49 /mes",
      limit: "500 documentos/mes",
      features: [
        "Equipo con roles",
        "Alertas de cuota",
        "Exportaciones PDF y Excel",
        "Historial 6 meses",
      ],
      popular: true,
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: "US$ 199 /mes",
      limit: "Ilimitado",
      features: [
        "Panel multi-tenant",
        "Auditoría avanzada",
        "Exportaciones masivas",
        "Gestión centralizada",
      ],
      popular: false,
    },
  ];

  /* -------------------------------------------------
     Manejadores de eventos
     ------------------------------------------------- */
  const handleLoad = () => {
    setLoadToast(true);
    setTimeout(() => {
      setLoadToast(false);
      alert("Redirigiendo al módulo de carga de facturas...");
    }, 1000);
  };

  const handleFlash = () => setFlashOpen(true);

  const handlePlanSelect = (plan) => {
    setSelectedPlan(plan);
    setTimeout(() => {
      alert(`Suscripción al plan ${plan.name} activada. ¡Gracias por confiar en NEXORA!`);
    }, 500);
  };

  return (
    <>
      {/* ============================
         Sección Superior: Hero + Viaje del Ahorro
         ============================ */}
      <section className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-7xl mx-auto px-4 py-12 grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">

          {/* ----------------------
             Columna Izquierda: Hero
             ---------------------- */}
          <div>
            {/* Badge flotante con pulso */}
            <div className="mb-6">
              <span
                className="inline-flex items-center gap-2 px-4 py-2 bg-black/30 backdrop-blur-sm border border-emerald-500/50 rounded-full animate-pulse"
              >
                <SparkIcon className="h-5 w-5" /> Auditoría Continua v2.0 Activa
              </span>
            </div>

            <h1
              className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent"
            >
              Bienvenido/a a NEXORA
            </h1>

            <p className="text-lg text-gray-300 mb-8 max-w-xl">
              Evita pagar de más en facturas y cotizaciones. Nuestra IA detecta alzas de precios ocultas y normaliza SKUs en CLP automáticamente antes de que pagues.
            </p>

            <div className="space-y-4">
              <button
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-8 py-3 rounded-full transition-all duration-300 shadow-lg shadow-emerald-200 hover:shadow-emerald-400"
                onClick={handleLoad}
              >
                Cargar documento ahora
              </button>
              <button
                className="bg-transparent border-2 border-emerald-400 hover:bg-emerald-600 text-emerald-400 font-medium px-8 py-3 rounded-full transition-all duration-300"
                onClick={() => window.alert("Funcionalidad de tutorial en desarrollo.")}
              >
                Ver tutorial interactivo
              </button>
            </div>
          </div>

          {/* ----------------------
             Columna Derecha: Tarjeta "El Viaje del Ahorro"
             ---------------------- */}
          <div className="relative">
            <div
              className="bg-black/50 backdrop-blur-sm border border-emerald-500/30 rounded-2xl p-6 max-w-md"
            >
              <h2 className="text-xl font-semibold mb-6 text-center">
                El Viaje del Ahorro
              </h2>

              <div className="space-y-4">
                {steps.map((step) => (
                  <div
                    key={step.id}
                    className="flex items-start gap-4 bg-white/5 rounded-xl p-4 backdrop-blur-sm border border-emerald-500/20"
                  >
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-emerald-500/20 border border-emerald-400/50"
                    >
                      {step.icon}
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium mb-1">{step.title}</h3>
                      <p className="text-sm text-gray-400">{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-8 text-center">
                <button
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-6 py-3 rounded-full transition-all duration-300 shadow-lg shadow-emerald-200 hover:shadow-emerald-400"
                  onClick={handleFlash}
                >
                  ▶ Ver demo flash (30s)
                </button>
              </div>
            </div>

            {/* Modal de demo flash (fullscreen overlay) */}
            {flashOpen && (
              <div
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
              >
                <div
                  className="bg-white/80 backdrop-blur-sm rounded-2xl p-8 w-full max-w-lg max-h-[80vh] overflow-y-auto"
                >
                  <button
                    className="absolute top-4 right-4 text-gray-500 hover:text-gray-800 text-2xl font-bold"
                    onClick={() => setFlashOpen(false)}
                  >
                    ✕
                  </button>

                  <h3 className="text-2xl font-bold mb-6 text-center">
                    Demo Flash - NEXORA
                  </h3>

                  <p className="text-gray-600 mb-4 text-center">
                    Simulador de flujo de auditoría continua
                  </p>

                  <div className="space-y-4">
                    {steps.map((step) => (
                      <p key={step.id} className="text-sm">
                        <strong>{step.title}</strong>: {step.description}
                      </p>
                    ))}
                  </div>

                  <div className="mt-8 flex justify-center">
                    <button
                      className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-6 py-3 rounded-full"
                      onClick={() => setFlashOpen(false)}
                    >
                      Cerrar
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ============================
         Sección Inferior: Precios (Grid 3 columnas)
         ============================ */}
      <section className="mt-12">
        <div className="max-w-7xl mx-auto px-4">
          <div
            className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full"
          >
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`bg-black/50 backdrop-blur-sm border border-emerald-500/30 rounded-2xl p-6 transition-all duration-300 hover:border-emerald-500/50 hover:shadow-lg hover:shadow-emerald-200 ${
                  plan.popular
                    ? "border-emerald-500/80 shadow-lg shadow-emerald-200"
                    : "shadow-sm"
                }`}
              >
                <h3 className="text-xl font-bold mb-3">
                  {plan.name} {plan.popular && (
                    <span
                      className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-600/20 text-emerald-400 text-xs rounded"
                    >
                      Más Popular
                    </span>
                  )}
                </h3>
                <p className="text-lg font-medium mb-4">{plan.price}</p>
                <p className="text-gray-400 mb-4">{plan.limit}</p>
                <ul className="space-y-2 text-sm text-gray-300">
                  {plan.features.map((feat) => (
                    <li key={feat}>{feat}</li>
                  ))}
                </ul>
                <button
                  className="mt-4 w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 rounded-full transition-all duration-300"
                  onClick={() => handlePlanSelect(plan)}
                >
                  Contratar
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}