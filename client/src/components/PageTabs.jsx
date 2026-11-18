import { motion } from "framer-motion";

export default function PageTabs({ tabs, active, onChange, label = "Secciones" }) {
  if (!tabs?.length) return null;

  return (
    <div className="page-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={`page-tab ${selected ? "active" : ""}`}
            onClick={() => onChange?.(tab.id)}
          >
            {selected ? (
              <motion.span
                className="page-tab-pill"
                layoutId={`page-tab-pill-${label}`}
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            ) : null}
            {Icon ? <Icon /> : null}
            <span className="page-tab-label">{tab.label}</span>
            {tab.badge ? <span className="page-tab-badge">{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
