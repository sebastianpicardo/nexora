import { useEffect } from "react";
import { ArrowRightIcon, HelpIcon, XIcon } from "./Icons";
import { getModuleHelp } from "../lib/moduleHelp";

export default function ModuleHelp({ view, onClose, onNavigate }) {
  const content = getModuleHelp(view);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!content) return null;

  return (
    <div className="modal-overlay help-guide-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal help-guide" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div className="help-guide-heading">
            <span className="help-guide-icon"><HelpIcon /></span>
            <div>
              <div className="topbar-eyebrow">{content.eyebrow}</div>
              <h2>{content.title}</h2>
            </div>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar ayuda">
            <XIcon />
          </button>
        </div>

        <div className="modal-body help-guide-body">
          <p className="help-guide-purpose">{content.purpose}</p>

          <div className="help-guide-section">
            <h3>Cómo usarlo en 4 pasos</h3>
            <ol className="help-guide-steps">
              {content.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>

          <div className="help-guide-section">
            <h3>Buenas prácticas</h3>
            <ul className="help-guide-tips">
              {content.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </div>

          {content.related?.length ? (
            <div className="help-guide-section">
              <h3>Continúa en</h3>
              <div className="help-guide-links">
                {content.related.map((link) => (
                  <button
                    key={link.id}
                    type="button"
                    className="help-guide-link"
                    onClick={() => {
                      onNavigate(link.id);
                      onClose();
                    }}
                  >
                    {link.label}
                    <ArrowRightIcon />
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="help-guide-foot">
            ¿Necesitas más detalle? Abre el asistente flotante y pregunta por este módulo.
          </div>
        </div>
      </div>
    </div>
  );
}
