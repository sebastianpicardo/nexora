export default function EmptyState({ title, description, actionLabel, onAction }) {
  return (
    <div className="empty-state-card">
      <div className="empty-state-icon">NEXORA</div>
      <h3>{title}</h3>
      {description ? <p className="muted">{description}</p> : null}
      {actionLabel && onAction ? (
        <button type="button" className="primary-button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
