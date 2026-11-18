const STEPS = [
  { id: 1, label: "Sube tus cotizaciones" },
  { id: 2, label: "Revisa alertas de sobreprecio" },
  { id: 3, label: "Aprueba la compra" },
];

export default function QuickGuide({ activeStep = 1 }) {
  return (
    <aside className="quick-guide" aria-label="Guía rápida del flujo de compras">
      <span className="quick-guide-kicker">Guía rápida</span>
      <ol className="quick-guide-steps">
        {STEPS.map((step) => {
          const active = step.id === activeStep;
          return (
            <li
              key={step.id}
              className={`quick-guide-step ${active ? "active" : ""} ${step.id < activeStep ? "done" : ""}`}
              aria-current={active ? "step" : undefined}
            >
              <span className="quick-guide-number">{step.id < activeStep ? "✓" : step.id}</span>
              <span>{step.label}</span>
              {active ? <span className="quick-guide-here">Estás aquí</span> : null}
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
