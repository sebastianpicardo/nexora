export default function StatCard({ label, value, detail, tone = "default", icon = null }) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-top">
        <div className="stat-label">{label}</div>
        {icon ? <span className="stat-icon">{icon}</span> : null}
      </div>
      <div className="stat-value">{value}</div>
      {detail ? <div className="stat-detail">{detail}</div> : null}
    </article>
  );
}
