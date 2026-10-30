import { formatDate, percent } from "../lib/format";

export default function QuotaCard({ quota, planName = "Free", compact = false }) {
  if (!quota) return null;
  const used = quota.used ?? 0;
  const limit = quota.limit;
  const width = quota.unlimited ? 100 : Math.min(Number(quota.percentage) || 0, 100);
  const tone = quota.exceeded ? "danger" : quota.warning ? "warning" : "ok";

  return (
    <div className={`quota-card ${compact ? "compact" : ""}`}>
      <div className="quota-head">
        <div>
          <div className="quota-eyebrow">Uso del plan {planName}</div>
          <div className="quota-value">
            {used} {quota.unlimited ? "documentos" : `de ${limit} documentos`}
          </div>
        </div>
        <span className={`quota-pill ${tone}`}>{quota.unlimited ? "Ilimitado" : percent(width, 0)}</span>
      </div>
      <div className="quota-track">
        <span className={`quota-fill ${tone}`} style={{ width: `${width}%` }} />
      </div>
      <div className="quota-foot">
        <span>
          {quota.unlimited
            ? "Sin límite mensual"
            : quota.remaining === 0
              ? "Límite alcanzado"
              : `Quedan ${quota.remaining} documentos`}
        </span>
        <span>Hasta {formatDate(quota.period_end)}</span>
      </div>
      {quota.warning ? (
        <div className="quota-warning">
          {quota.exceeded
            ? "Actualiza tu plan para seguir cargando documentos."
            : "Estás cerca del límite mensual de tu plan."}
        </div>
      ) : null}
    </div>
  );
}
