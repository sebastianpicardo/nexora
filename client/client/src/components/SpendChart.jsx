import { formatMoney, formatMonth, percent } from "../lib/format";

export default function SpendChart({ data = [], currency = "CLP" }) {
  if (!data.length) {
    return <div className="empty-state">Aún no hay actividad mensual para graficar.</div>;
  }

  const width = 660;
  const height = 230;
  const padding = { top: 20, right: 28, bottom: 34, left: 12 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const maxSpend = Math.max(...data.map((row) => Number(row.spend) || 0), 1);
  const barGap = 18;
  const barWidth = Math.max((chartWidth - barGap * (data.length - 1)) / data.length, 20);

  const points = data.map((row, index) => {
    const x = padding.left + index * (barWidth + barGap) + barWidth / 2;
    const y = padding.top + chartHeight - (Math.min(Number(row.alert_rate) || 0, 100) / 100) * chartHeight;
    return { x, y, row };
  });
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="chart-shell">
      <div className="chart-legend">
        <span><i className="legend-bar" /> Compra mensual</span>
        <span><i className="legend-line" /> % alertas</span>
      </div>
      <svg className="spend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Compras y alertas por mes">
        <defs>
          <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10B981" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#06B6D4" stopOpacity="0.25" />
          </linearGradient>
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#F59E0B" stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + chartHeight * ratio;
          return <line key={ratio} x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="chart-grid-line" />;
        })}

        {data.map((row, index) => {
          const value = Number(row.spend) || 0;
          const barHeight = Math.max((value / maxSpend) * chartHeight, value > 0 ? 4 : 0);
          const x = padding.left + index * (barWidth + barGap);
          const y = padding.top + chartHeight - barHeight;
          return (
            <g key={row.month}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                rx={7}
                fill="url(#barGradient)"
                className="chart-bar"
              >
                <title>{`${formatMonth(row.month)}: ${formatMoney(value, currency)}`}</title>
              </rect>
              <text x={x + barWidth / 2} y={height - 12} textAnchor="middle" className="chart-label">
                {formatMonth(row.month)}
              </text>
            </g>
          );
        })}

        <polygon
          points={`${padding.left + barWidth / 2},${padding.top + chartHeight} ${line} ${
            padding.left + (data.length - 1) * (barWidth + barGap) + barWidth / 2
          },${padding.top + chartHeight}`}
          fill="url(#areaGradient)"
        />
        <polyline points={line} className="chart-line" />
        {points.map((point) => (
          <circle key={point.row.month} cx={point.x} cy={point.y} r="3.5" className="chart-dot">
            <title>{`${formatMonth(point.row.month)}: ${percent(point.row.alert_rate, 1)} de alertas`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
