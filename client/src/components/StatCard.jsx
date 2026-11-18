import { TrendUpIcon, TrendDownIcon } from "./Icons";

function Sparkline({ values = [], tone = "brand" }) {
  if (!values?.length) return null;
  const points = values.map((value, index) => {
    const x = (index / Math.max(1, values.length - 1)) * 100;
    const y = 28 - (Number(value) / Math.max(1, Math.max(...values.map(Number)))) * 24;
    return `${x},${Math.max(2, Math.min(26, y))}`;
  });
  const d = `M${points.join(" L")}`;
  return (
    <svg
      className="stat-sparkline"
      viewBox="0 0 100 30"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path className={`stat-spark-area tone-${tone}`} d={`${d} L100,30 L0,30 Z`} />
      <path className={`stat-spark-line tone-${tone}`} d={d} />
    </svg>
  );
}

export default function StatCard({
  label,
  value,
  detail,
  tone = "default",
  icon = null,
  trend = null,
  trendHint = null,
  sparkline = null,
}) {
  const trendUp = Number(trend) >= 0;
  const hasTrend = trend !== null && trend !== undefined && !Number.isNaN(Number(trend));

  return (
    <article className={`stat-card tone-${tone}`}>
      <div className="stat-top">
        <div className="stat-label">{label}</div>
        {icon ? <span className="stat-icon">{icon}</span> : null}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-foot">
        <div className="stat-detail">
          {hasTrend ? (
            <span className={`stat-trend ${trendUp ? "up" : "down"}`}>
              {trendUp ? <TrendUpIcon /> : <TrendDownIcon />}
              {Math.abs(Number(trend)).toFixed(1)}%
            </span>
          ) : null}
          {detail ? <span>{detail}</span> : null}
          {trendHint ? <span className="stat-trend-hint">{trendHint}</span> : null}
        </div>
        {sparkline ? <Sparkline values={sparkline} tone={tone} /> : null}
      </div>
    </article>
  );
}
