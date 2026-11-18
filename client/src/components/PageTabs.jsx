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
            {Icon ? <Icon /> : null}
            <span>{tab.label}</span>
            {tab.badge ? <span className="page-tab-badge">{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
