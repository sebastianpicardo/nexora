const DEFAULT_STEPS = [
  { id: 1, label: "Sube tus cotizaciones" },
  { id: 2, label: "Revisa alertas de sobreprecio" },
  { id: 3, label: "Aprueba la compra" },
];

export default function QuickGuide({ steps: stepsProp = DEFAULT_STEPS, activeStep = 1 }) {
  const steps = Array.isArray(stepsProp) && stepsProp.length > 0 ? stepsProp : DEFAULT_STEPS;

  return (
    <aside className="quick-guide" aria-label="Guía rápida del flujo de compras">
      <span className="quick-guide-kicker">Guía rápida</span>
      <ol className="quick-guide-steps">
        {steps.map((step) => {
          const stepIsActive = step.id === activeStep;
          const stepIsCompleted = step.id < activeStep;
          return (
            <li
              key={step.id}
              className={`quick-guide-step ${stepIsActive ? "active" : ""} ${stepIsCompleted ? "done" : ""}`}
              aria-current={stepIsActive ? "step" : undefined}
            >
              <span className="quick-guide-number">
                {stepIsCompleted ? "" : step.id}
              </span>
              <span>{step.label}</span>
              {stepIsActive ? (
                <span className="quick-guide-here">Estás aquí</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </aside>
  );
}

QuickGuide.defaultProps = {
  steps: DEFAULT_STEPS,
  activeStep: 1,
};