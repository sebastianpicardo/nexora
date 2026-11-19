import { formatMoney } from "../lib/format";
import { ArrowRightIcon, CheckIcon, SparkIcon, TrendUpIcon } from "./Icons";

export default function SavingsSpotlight({ summary, currency = "CLP", onNavigate }) {
  const detected = Number(summary?.potential_savings ?? summary?.total_savings ?? 0);
  const verified = Number(summary?.verified_savings ?? summary?.total_savings ?? 0);
  const pending = Number(
    summary?.pending_savings ?? Math.max(detected - verified, 0),
  );
  const hasActivity = Number(summary?.items_total || 0) > 0;
  const noSavings = detected <= 0 && verified <= 0 && pending <= 0;

  return (
    <section className="card savings-spotlight">
      <div className="savings-spotlight-head">
        <div>
          <div className="eyebrow"><SparkIcon /> Ahorro en CLP</div>
          <h2>La plata que NEXORA ya te está cuidando</h2>
          <p>
            {noSavings
              ? hasActivity
                ? "Todavía no hay sobrecostos detectados. Para calcularlos necesitas compras repetidas del mismo producto o cargar el RCV."
                : "Carga tus documentos o el ejemplo de ferretería de 90 días para ver cuánto puedes recuperar."
              : "Separa lo que ya ganaste de lo que todavía puedes recuperar con una mejor compra o negociación."}
          </p>
        </div>
        <button
          type="button"
          className="button ghost small"
          onClick={() => onNavigate?.("audit-express")}
        >
          Abrir Auditoría <ArrowRightIcon />
        </button>
      </div>

      <div className="savings-spotlight-grid">
        <div className="savings-highlight primary">
          <span><SparkIcon /> Ahorro detectado</span>
          <strong>{formatMoney(detected, currency)}</strong>
          <small>Mejor proveedor, renegociación y alzas sobre mediana.</small>
        </div>
        <div className="savings-highlight ok">
          <span><CheckIcon /> Ahorro verificado</span>
          <strong>{formatMoney(verified, currency)}</strong>
          <small>Con evidencia auditable para gerencia o contador.</small>
        </div>
        <div className="savings-highlight warning">
          <span><TrendUpIcon /> Por recuperar</span>
          <strong>{formatMoney(pending, currency)}</strong>
          <small>Oportunidades abiertas que aún no cierras.</small>
        </div>
      </div>
    </section>
  );
}
