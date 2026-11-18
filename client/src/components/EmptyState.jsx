export default function EmptyState({ title, description, actionLabel, onAction, icon = null }) {
  return (
    <div className="empty-state-card">
      <div className="empty-state-icon">{icon || "NEXORA"}</div>
      <h3>{title}</h3>
      {description ? <p className="muted">{description}</p> : null}
      {actionLabel && onAction ? (
        <button type="button" className="button primary cta-gradient" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
