import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import { formatDate, formatMoney, labelize } from "../lib/format";
import PageTabs from "../components/PageTabs";
import StatCard from "../components/StatCard";
import RcvCompletenessPanel from "../components/RcvCompletenessPanel";
import {
  AlertTriangleIcon,
  CheckIcon,
  DocumentsIcon,
  DownloadIcon,
  PricesIcon,
  SearchIcon,
  SparkIcon,
  TrendUpIcon,
  UploadIcon,
} from "../components/Icons";

const TABS = [
  { id: "diagnostico", label: "Diagnóstico", icon: SparkIcon },
  { id: "comparador", label: "Comparador", icon: SearchIcon },
  { id: "negociacion", label: "Negociación", icon: PricesIcon },
  { id: "informe", label: "Informe semanal", icon: TrendUpIcon },
  { id: "rcv", label: "Importar RCV", icon: UploadIcon },
];

const DAY_OPTIONS = [30, 90, 180, 365];

function severityLabel(value) {
  return {
    critical: "Crítico",
    high: "Alto",
    medium: "Medio",
    low: "Bajo",
  }[value] || value;
}

function money(value, currency) {
  if (value === null || value === undefined) return "—";
  return formatMoney(Number(value), currency || "CLP");
}

export default function AuditExpressPage({ onNavigate }) {
  const { user, organization, canManage } = useAuth();
  const currency = organization?.default_currency || "CLP";
  const canImport = ["owner", "admin", "analyst"].includes(user?.role || "");

  const [tab, setTab] = useState("diagnostico");
  const [days, setDays] = useState(90);
  const [audit, setAudit] = useState(null);
  const [comparator, setComparator] = useState(null);
  const [negotiation, setNegotiation] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [rcvFile, setRcvFile] = useState(null);
  const [rcvApply, setRcvApply] = useState(false);
  const [rcvResult, setRcvResult] = useState(null);
  const [rcvBusy, setRcvBusy] = useState(false);
  const [rcvError, setRcvError] = useState("");
  const [onboarding, setOnboarding] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoNotice, setDemoNotice] = useState("");

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [auditResult, comparatorResult, negotiationResult, weeklyResult, onboardingResult, radarResult] =
        await Promise.allSettled([
          api(`/api/leaks/audit?days=${days}`),
          api("/api/leaks/comparator?limit=40"),
          api("/api/leaks/negotiation?limit=25"),
          api("/api/leaks/weekly-report"),
          api("/api/enterprise/onboarding"),
          api("/api/compra-agil/opportunities?limit=100"),
        ]);
      if (auditResult.status === "rejected") throw auditResult.reason;
      setAudit(auditResult.value);
      setComparator(comparatorResult.status === "fulfilled" ? comparatorResult.value : null);
      setNegotiation(negotiationResult.status === "fulfilled" ? negotiationResult.value : null);
      setWeekly(weeklyResult.status === "fulfilled" ? weeklyResult.value : null);
      setOnboarding(onboardingResult.status === "fulfilled" ? onboardingResult.value : null);
      setOpportunities(
        radarResult.status === "fulfilled" ? radarResult.value.opportunities || [] : [],
      );
    } catch (err) {
      setError(err.message || "No se pudo cargar la auditoría.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function seedDemo() {
    setDemoBusy(true);
    setError("");
    setDemoNotice("");
    try {
      await api("/api/enterprise/onboarding/demo?months=3", { method: "POST", body: "{}" });
      setDemoNotice("Datos de ejemplo cargados: 90 días de compras demo con proveedores, precios y márgenes (seed.sql).");
      await loadAll();
    } catch (err) {
      setError(err.message || "No se pudo cargar el ejemplo de ferretería.");
    } finally {
      setDemoBusy(false);
    }
  }

  async function clearDemo() {
    setDemoBusy(true);
    setError("");
    setDemoNotice("");
    try {
      await api("/api/enterprise/onboarding/demo", { method: "DELETE" });
      setDemoNotice("Datos de ejemplo eliminados: se borran documentos, catálogo, proveedores y configuración de seed. Puedes cargar tus propios documentos.");
      await loadAll();
    } catch (err) {
      setError(err.message || "No se pudieron limpiar los datos de ejemplo.");
    } finally {
      setDemoBusy(false);
    }
  }

  const findings = audit?.findings || [];
  const summary = audit?.summary || {};
  const actionPlan = audit?.action_plan || [];
  const coverage = audit?.coverage || {};
  const demoSeeded = Boolean(onboarding?.demo_seeded);
  const recoverToday =
    Number(summary.price_overpay || 0) + Number(summary.invoice_discrepancy || 0);
  const marginProtected = Number(summary.margin_bleed || 0);
  const secured = Number(summary.realized_savings || 0);
  const salesPotential = opportunities.reduce(
    (total, item) => total + Number(item.budget_clp || 0),
    0,
  );
  const hasCoverage = Number(coverage.documents || 0) > 0;
  const metricsAtZero =
    recoverToday <= 0 && marginProtected <= 0 && secured <= 0 && findings.length === 0;
  const showDemoCta = canManage && (!hasCoverage || metricsAtZero);
  const marginFindings = findings.filter((item) => item.category === "margin_bleed").length;
  const priceFindings = findings.filter((item) => item.category === "price_overpay").length;
  const invoiceFindings = findings.filter((item) => item.category === "invoice_discrepancy").length;
  const currencyLabel = audit?.currency || currency;
  const filterValue = search.trim().toLowerCase();
  const filteredComparisons = useMemo(() => {
    const items = comparator?.items || [];
    if (!filterValue) return items;
    return items.filter(
      (item) =>
        String(item.product || "").toLowerCase().includes(filterValue) ||
        String(item.sku || "").toLowerCase().includes(filterValue) ||
        String(item.category || "").toLowerCase().includes(filterValue),
    );
  }, [comparator, filterValue]);

  async function runRcv(apply) {
    if (!rcvFile) {
      setRcvError("Selecciona un archivo del RCV.");
      return;
    }
    setRcvBusy(true);
    setRcvError("");
    try {
      const form = new FormData();
      form.append("file", rcvFile);
      form.append("apply", apply ? "true" : "false");
      const result = await api("/api/leaks/rcv", { method: "POST", body: form });
      setRcvResult(result);
      if (apply) loadAll();
    } catch (err) {
      setRcvError(err.message || "No se pudo procesar el archivo.");
    } finally {
      setRcvBusy(false);
    }
  }

  return (
    <div className="page-stack audit-page">
      <section className="page-intro audit-hero audit-hero-rich">
        <div className="audit-hero-copy">
          <div className="eyebrow">
            Auditoría Express · {days} días
            {demoSeeded ? <span className="audit-demo-tag">Datos de ejemplo</span> : null}
          </div>
          <h2>Aquí está la plata que puedes recuperar y ganar esta semana</h2>
          <p>
            {hasCoverage
              ? `Detectamos ${money(recoverToday, currencyLabel)} recuperables por precios y hasta ${money(
                  marginProtected,
                  currencyLabel,
                )} de margen que puedes proteger al ajustar tu lista de precios.`
              : "Carga tus facturas, listas o el RCV, o parte con un ejemplo de ferretería para ver montos reales en menos de un minuto."}
          </p>
          <div className="audit-hero-chips">
            <span>
              <PricesIcon /> Sobrecostos: {money(summary.price_overpay, currencyLabel)}
            </span>
            <span>
              <TrendUpIcon /> Margen en riesgo: {money(marginProtected, currencyLabel)}
            </span>
            <span>
              <AlertTriangleIcon />{" "}
              {hasCoverage
                ? `Fuga ${summary.leakage_pct || 0}% sobre ${money(summary.spend_total, currencyLabel)}`
                : "Sin compras auditadas todavía"}
            </span>
          </div>
          <div className="audit-hero-actions">
            {showDemoCta ? (
              <button
                type="button"
                className="button primary"
                onClick={seedDemo}
                disabled={demoBusy}
              >
                <SparkIcon />{" "}
                {demoBusy ? "Cargando ejemplo…" : "Cargar ejemplo de ferretería (90 días)"}
              </button>
            ) : (
              <button
                type="button"
                className="button primary"
                onClick={() =>
                  downloadFile(
                    `/api/leaks/audit.pdf?days=${days}`,
                    "auditoria_express_nexora.pdf",
                  )
                }
              >
                <DownloadIcon /> Descargar informe PDF
              </button>
            )}
            {demoSeeded ? (
              <button type="button" className="button ghost" onClick={clearDemo} disabled={demoBusy}>
                Limpiar datos de ejemplo
              </button>
            ) : null}
            {onNavigate ? (
              <button
                type="button"
                className="button ghost"
                onClick={() => onNavigate("purchases")}
              >
                <DocumentsIcon /> Cargar documentos
              </button>
            ) : null}
            <button type="button" className="button ghost" onClick={() => setTab("rcv")}>
              <UploadIcon /> Importar RCV
            </button>
            <button type="button" className="button ghost" onClick={loadAll}>
              Actualizar análisis
            </button>
          </div>
        </div>
        <div className="audit-money-card">
          <span className="audit-money-eyebrow">Puedes recuperar hoy</span>
          <strong>{loading && !audit ? "—" : money(recoverToday, currencyLabel)}</strong>
          <div className="audit-money-rows">
            <div>
              <span>Diferencia entre proveedores</span>
              <b>{money(summary.price_overpay, currencyLabel)}</b>
            </div>
            <div>
              <span>Facturas por conciliar</span>
              <b>{money(summary.invoice_discrepancy, currencyLabel)}</b>
            </div>
            <div>
              <span>Margen que proteges</span>
              <b>{money(marginProtected, currencyLabel)}</b>
            </div>
          </div>
          <div className="audit-money-secured">
            <CheckIcon />
            <span>
              Ahorro ya asegurado
              <b>{money(secured, currencyLabel)}</b>
            </span>
          </div>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {demoNotice ? <div className="alert success">{demoNotice}</div> : null}

      <section className="stats-grid audit-stats">
        <StatCard
          label="Recuperable hoy"
          value={loading && !audit ? "—" : money(recoverToday, currencyLabel)}
          detail={
            priceFindings
              ? `${priceFindings} productos con sobreprecio detectado`
              : findings.length
                ? "Hay hallazgos sin monto: faltan precios o volumen para estimarlo"
                : "Sin sobrecostos detectados en la ventana"
          }
          tone="ok"
          icon={<SparkIcon />}
        />
        <StatCard
          label="Margen que proteges"
          value={loading && !audit ? "—" : money(marginProtected, currencyLabel)}
          detail={
            marginFindings
              ? `${marginFindings} productos bajo el margen objetivo`
              : "Todos los márgenes están sobre el mínimo"
          }
          tone="warning"
          icon={<PricesIcon />}
        />
        <StatCard
          label="Ahorro ya asegurado"
          value={loading && !audit ? "—" : money(secured, currencyLabel)}
          detail={
            secured > 0
              ? "Verificado con evidencia y documento de respaldo"
              : hasCoverage
                ? "Cierra una negociación y registra el ahorro verificado"
                : "Aún no hay documentos auditados"
          }
          tone="brand"
          icon={<CheckIcon />}
        />
        <StatCard
          label="Nuevas ventas · Compra Ágil"
          value={loading && !audit ? "—" : money(salesPotential, currencyLabel)}
          detail={
            opportunities.length
              ? `${opportunities.length} oportunidades abiertas para cotizar`
              : "Sin oportunidades cargadas: importa un CSV o conecta la API"
          }
          icon={<TrendUpIcon />}
        />
      </section>

      <p className="audit-coverage-note">
        {hasCoverage
          ? `Analizando ${coverage.documents} documentos, ${coverage.items} ítems y ${coverage.suppliers} proveedores · ${coverage.catalog_items || 0} productos en catálogo.`
          : "Aún no hay compras auditadas. Carga documentos, importa el RCV o usa el ejemplo de ferretería para ver el impacto en CLP."}
        {invoiceFindings
          ? ` Hay ${invoiceFindings} diferencias de factura por conciliar que podrían ajustar el monto recuperable.`
          : ""}
      </p>

      <div className="audit-toolbar">
        <PageTabs tabs={TABS} active={tab} onChange={setTab} label="Auditoría Express" />
        <div className="audit-window">
          <span>Ventana</span>
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={`chip ${days === option ? "active" : ""}`}
              onClick={() => setDays(option)}
            >
              {option}d
            </button>
          ))}
        </div>
      </div>

      {tab === "diagnostico" ? (
        <div className="audit-grid">
          <section className="card audit-findings-card">
            <div className="card-head">
              <div>
                <h2>Hallazgos priorizados</h2>
                <p>Cada fila indica cuánto puedes recuperar o corregir.</p>
              </div>
              <span className="badge">{findings.length}</span>
            </div>
            {findings.length ? (
              <div className="table-wrap">
                <table className="data-table audit-table">
                  <thead>
                    <tr>
                      <th>Prioridad</th>
                      <th>Hallazgo</th>
                      <th>Proveedor</th>
                      <th className="right">Actual</th>
                      <th className="right">Referencia</th>
                      <th className="right">Ahorro est.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.map((finding) => (
                      <tr key={finding.id}>
                        <td>
                          <span className={`badge severity-${finding.severity}`}>
                            {severityLabel(finding.severity)}
                          </span>
                          <div className="audit-category">{finding.category_label}</div>
                        </td>
                        <td>
                          <strong>{finding.title}</strong>
                          <div className="muted small">{finding.detail}</div>
                          <div className="audit-action">{finding.action}</div>
                        </td>
                        <td>{finding.supplier || "—"}</td>
                        <td className="right mono">
                          {money(finding.current_price, finding.currency)}
                        </td>
                        <td className="right mono">
                          {money(finding.reference_price, finding.currency)}
                        </td>
                        <td className="right mono">
                          {finding.savings ? money(finding.savings, finding.currency) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="audit-empty">
                <CheckIcon />
                <h3>Sin fugas detectadas con los datos actuales</h3>
                <p>
                  Carga facturas y listas de precios de al menos dos proveedores para activar la
                  comparación automática.
                </p>
              </div>
            )}
          </section>

          <aside className="stack">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Plan de acción</h2>
                  <p>Siguiente mejor movimiento, en orden.</p>
                </div>
              </div>
              <div className="audit-plan">
                {actionPlan.map((step, index) => (
                  <div key={`${step.title}-${index}`} className="audit-plan-item">
                    <span className="audit-plan-index">{index + 1}</span>
                    <div>
                      <strong>{step.title}</strong>
                      <p>{step.detail}</p>
                      <div className="audit-plan-meta">
                        <span className="badge">{step.priority}</span>
                        <span className="muted small">Responsable: {step.owner_role}</span>
                        {step.expected_saving ? (
                          <span className="muted small">
                            Ahorro: {money(step.expected_saving, audit?.currency)}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="card audit-coverage">
              <div className="card-head">
                <div>
                  <h2>Cobertura del análisis</h2>
                  <p>Qué datos se usaron para el diagnóstico.</p>
                </div>
              </div>
              <dl className="audit-coverage-list">
                <div><dt>Documentos</dt><dd>{audit?.coverage?.documents || 0}</dd></div>
                <div><dt>Ítems con precio</dt><dd>{audit?.coverage?.items || 0}</dd></div>
                <div><dt>Proveedores</dt><dd>{audit?.coverage?.suppliers || 0}</dd></div>
                <div><dt>Productos en catálogo</dt><dd>{audit?.coverage?.catalog_items || 0}</dd></div>
                <div><dt>Revisión pendiente</dt><dd>{audit?.coverage?.pending_review || 0}</dd></div>
                <div>
                  <dt>Último dato</dt>
                  <dd>{audit?.coverage?.last_date ? formatDate(audit.coverage.last_date) : "—"}</dd>
                </div>
              </dl>
              <div className="audit-assumptions">
                <strong>Supuestos</strong>
                <ul>
                  {(audit?.assumptions || []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </section>
          </aside>
        </div>
      ) : null}

      {tab === "comparador" ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Comparador de precios por proveedor</h2>
              <p>Último precio vigente de cada proveedor en los últimos 90 días.</p>
            </div>
            <label className="search-field">
              <SearchIcon />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar producto, SKU o categoría"
              />
            </label>
          </div>
          {filteredComparisons.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Mejor proveedor</th>
                    <th className="right">Mejor precio</th>
                    <th className="right">Peor precio</th>
                    <th className="right">Brecha</th>
                    <th className="right">Margen catálogo</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredComparisons.map((item) => (
                    <tr key={`${item.product}-${item.unit}`}>
                      <td>
                        <strong>{item.product}</strong>
                        <div className="muted small">
                          {item.sku || "Sin SKU"} · {item.unit || "unidad"}
                          {item.category ? ` · ${item.category}` : ""}
                        </div>
                      </td>
                      <td>
                        {item.best_supplier}
                        <div className="muted small">{item.suppliers.length} proveedores</div>
                      </td>
                      <td className="right mono">{money(item.best_price, comparator?.currency)}</td>
                      <td className="right mono">{money(item.worst_price, comparator?.currency)}</td>
                      <td className="right">
                        <span className="badge severity-medium">{item.spread_pct}%</span>
                      </td>
                      <td className="right mono">
                        {item.catalog ? `${item.catalog.margin_pct}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="audit-empty">
              <SearchIcon />
              <h3>Sin comparaciones todavía</h3>
              <p>Carga precios de al menos dos proveedores para comparar un mismo producto.</p>
            </div>
          )}
        </section>
      ) : null}

      {tab === "negociacion" ? (
        <div className="audit-grid">
          <section className="card audit-findings-card">
            <div className="card-head">
              <div>
                <h2>Hoja de negociación</h2>
                <p>
                  Precio objetivo = mejor precio vigente + 2%. Ahorro estimado con el volumen de la
                  última compra.
                </p>
              </div>
              <span className="badge">
                {money(negotiation?.total_estimated_savings, negotiation?.currency)}
              </span>
            </div>
            {(negotiation?.suppliers || []).length ? (
              <div className="audit-suppliers">
                {negotiation.suppliers.map((supplier) => (
                  <div key={supplier.supplier} className="audit-supplier">
                    <div className="audit-supplier-head">
                      <div>
                        <strong>{supplier.supplier}</strong>
                        <div className="muted small">
                          {supplier.items.length} productos a renegociar
                        </div>
                      </div>
                      <div className="audit-supplier-total">
                        <span className="muted small">Ahorro estimado</span>
                        <strong>{money(supplier.estimated_savings, negotiation.currency)}</strong>
                      </div>
                    </div>
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Producto</th>
                            <th className="right">Precio actual</th>
                            <th className="right">Objetivo</th>
                            <th className="right">Brecha</th>
                            <th>Mejor proveedor</th>
                          </tr>
                        </thead>
                        <tbody>
                          {supplier.items.map((item) => (
                            <tr key={`${supplier.supplier}-${item.product}`}>
                              <td>
                                {item.product}
                                <div className="muted small">{item.sku || "Sin SKU"}</div>
                              </td>
                              <td className="right mono">
                                {money(item.current_price, negotiation.currency)}
                              </td>
                              <td className="right mono">
                                {money(item.target_price, negotiation.currency)}
                              </td>
                              <td className="right">{item.gap_pct}%</td>
                              <td>{item.best_supplier}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="audit-empty">
                <PricesIcon />
                <h3>No hay productos con brecha suficiente</h3>
                <p>Necesitas al menos dos proveedores con precios vigentes del mismo producto.</p>
              </div>
            )}
            {negotiation?.note ? <p className="muted small">{negotiation.note}</p> : null}
          </section>

          <aside className="stack">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Cómo usar esta hoja</h2>
                  <p>Guion corto para la reunión con el proveedor.</p>
                </div>
              </div>
              <ol className="audit-guidelist">
                <li>Comparte el precio objetivo, no el nombre del competidor.</li>
                <li>Ofrece volumen o pago anticipado a cambio de la rebaja.</li>
                <li>Acuerda precio y vigencia por escrito antes de la próxima compra.</li>
                <li>Registra el ahorro en NEXORA para medir el resultado real.</li>
              </ol>
            </section>
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Resumen por proveedor</h2>
                </div>
              </div>
              <dl className="audit-coverage-list">
                <div>
                  <dt>Proveedores en la hoja</dt>
                  <dd>{negotiation?.suppliers?.length || 0}</dd>
                </div>
                <div>
                  <dt>Gasto actual comparado</dt>
                  <dd>
                    {money(
                      (negotiation?.suppliers || []).reduce(
                        (total, supplier) => total + Number(supplier.current_total || 0),
                        0,
                      ),
                      negotiation?.currency,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Ahorro estimado</dt>
                  <dd>{money(negotiation?.total_estimated_savings, negotiation?.currency)}</dd>
                </div>
              </dl>
            </section>
          </aside>
        </div>
      ) : null}

      {tab === "informe" ? (
        <div className="audit-grid">
          <section className="card audit-findings-card">
            <div className="card-head">
              <div>
                <h2>Informe semanal para gerencia</h2>
                <p>
                  Generado {weekly?.generated_at ? formatDate(weekly.generated_at) : "hoy"} ·
                  últimos 7 días.
                </p>
              </div>
              <button
                type="button"
                className="button ghost"
                onClick={() =>
                  downloadFile("/api/leaks/audit.pdf?days=7", "informe_semanal_nexora.pdf")
                }
              >
                <DownloadIcon /> PDF 7 días
              </button>
            </div>
            <div className="stats-grid audit-weekly-stats">
              <StatCard
                label="Documentos procesados"
                value={weekly?.summary?.documents_processed ?? 0}
                detail={`${weekly?.summary?.documents_failed || 0} con error`}
                icon={<DocumentsIcon />}
              />
              <StatCard
                label="Excepciones resueltas"
                value={weekly?.summary?.exceptions_resolved ?? 0}
                detail={`${weekly?.summary?.findings_total || 0} hallazgos nuevos`}
                icon={<CheckIcon />}
              />
              <StatCard
                label="Ahorro potencial"
                value={money(weekly?.summary?.potential_savings, weekly?.currency)}
                detail="detectado esta semana"
                tone="ok"
                icon={<SparkIcon />}
              />
              <StatCard
                label="Aprobaciones pendientes"
                value={weekly?.summary?.approvals_pending ?? 0}
                detail="requieren decisión"
                tone="warning"
                icon={<CheckIcon />}
              />
            </div>
            <div className="audit-highlights">
              <h3>Lo importante de la semana</h3>
              <ul>
                {(weekly?.highlights || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <h3>Top hallazgos</h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Prioridad</th>
                    <th>Hallazgo</th>
                    <th className="right">Ahorro est.</th>
                  </tr>
                </thead>
                <tbody>
                  {(weekly?.top_findings || []).map((finding) => (
                    <tr key={finding.id}>
                      <td>
                        <span className={`badge severity-${finding.severity}`}>
                          {severityLabel(finding.severity)}
                        </span>
                      </td>
                      <td>{finding.title}</td>
                      <td className="right mono">
                        {money(finding.savings, finding.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <aside className="stack">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Cómo enviarlo</h2>
                  <p>Un correo corto, tres números y una decisión.</p>
                </div>
              </div>
              <ol className="audit-guidelist">
                <li>Adjunta el PDF semanal.</li>
                <li>Destaca ahorro potencial y los 3 hallazgos principales.</li>
                <li>Pide aprobar la negociación con los proveedores indicados.</li>
                <li>Define responsable y fecha de revisión.</li>
              </ol>
            </section>
          </aside>
        </div>
      ) : null}

      {tab === "rcv" ? (
        <div className="page-stack">
          <RcvCompletenessPanel />
          <div className="audit-grid">
          <section className="card">
            <div className="card-head">
              <div>
                <h2>Importar Registro de Compras y Ventas (RCV)</h2>
                <p>
                  Sube el CSV o Excel del SII. Comparamos el costo declarado contra tu catálogo y
                  detectamos discrepancias.
                </p>
              </div>
            </div>
            <div className="audit-dropzone">
              <UploadIcon />
              <label className="audit-file">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.txt"
                  onChange={(event) => {
                    setRcvFile(event.target.files?.[0] || null);
                    setRcvResult(null);
                    setRcvError("");
                  }}
                />
                <span>{rcvFile ? rcvFile.name : "Seleccionar archivo RCV"}</span>
              </label>
              <p className="muted small">
                Acepta dos formatos: <strong>RCV de documentos</strong> (folio, tipo DTE, RUT,
                razón social, fecha, neto, IVA, total) o <strong>RCV de ítems</strong> (producto,
                unidad, cantidad, precio unitario o total). Máximo 25 MB.
              </p>
              {canImport ? (
                <label className="audit-checkbox">
                  <input
                    type="checkbox"
                    checked={rcvApply}
                    onChange={(event) => setRcvApply(event.target.checked)}
                  />
                  Actualizar costos del catálogo al importar (solo RCV de ítems)
                </label>
              ) : (
                <p className="muted small">
                  Tu rol puede previsualizar, pero no actualizar costos del catálogo.
                </p>
              )}
              {rcvError ? <div className="alert error">{rcvError}</div> : null}
              <div className="audit-hero-actions">
                <button
                  type="button"
                  className="button ghost"
                  disabled={rcvBusy}
                  onClick={() => runRcv(false)}
                >
                  Previsualizar
                </button>
                <button
                  type="button"
                  className="button primary"
                  disabled={rcvBusy || !canImport || !rcvApply || rcvResult?.rcv_type === "document"}
                  onClick={() => runRcv(true)}
                >
                  {rcvBusy ? "Procesando…" : "Importar y actualizar"}
                </button>
              </div>
            </div>

            {rcvResult ? (
              <div className="audit-rcv-result">
                {rcvResult.rcv_type === "document" ? (
                  <>
                    <div className="audit-rcv-counts">
                      <span className="badge">
                        Documentos: {rcvResult.rows?.length || 0}
                      </span>
                      <span className="badge">
                        Total:{" "}
                        {money(
                          (rcvResult.rows || []).reduce(
                            (sum, row) => sum + (Number(row.total) || 0),
                            0,
                          ),
                          rcvResult.currency,
                        )}
                      </span>
                    </div>
                    <p className="muted small">
                      RCV de documentos detectado (resumen por folio). Esta vista no modifica tu
                      catálogo; úsala para completitud y conciliación.
                    </p>
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Folio</th>
                            <th>Tipo DTE</th>
                            <th>RUT</th>
                            <th>Razón social</th>
                            <th>Fecha</th>
                            <th className="right">Neto</th>
                            <th className="right">IVA</th>
                            <th className="right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(rcvResult.rows || []).map((row) => (
                            <tr key={`${row.line}-${row.folio}`}>
                              <td className="mono">{row.folio}</td>
                              <td>{row.tipo_doc || "—"}</td>
                              <td className="mono">{row.rut_emisor || "—"}</td>
                              <td>{row.razon_social || "—"}</td>
                              <td>{row.fecha_documento ? formatDate(row.fecha_documento) : "—"}</td>
                              <td className="right mono">{money(row.neto, rcvResult.currency)}</td>
                              <td className="right mono">{money(row.iva, rcvResult.currency)}</td>
                              <td className="right mono">{money(row.total, rcvResult.currency)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="audit-rcv-counts">
                      <span className="badge">Nuevos: {rcvResult.counts?.nuevos || 0}</span>
                      <span className="badge">Actualizados: {rcvResult.counts?.actualizados || 0}</span>
                      <span className="badge">Sin cambio: {rcvResult.counts?.sin_cambio || 0}</span>
                      <span className="badge severity-medium">
                        Discrepancias: {rcvResult.counts?.discrepancias || 0}
                      </span>
                      <span className="badge">Sin precio: {rcvResult.counts?.sin_precio || 0}</span>
                    </div>
                    {rcvResult.truncated ? (
                      <div className="alert warning">
                        El archivo superó el límite y se procesó parcialmente.
                      </div>
                    ) : null}
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Producto</th>
                            <th>SKU</th>
                            <th className="right">Precio RCV</th>
                            <th className="right">Costo catálogo</th>
                            <th className="right">Diferencia</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(rcvResult.rows || []).map((row) => (
                            <tr key={`${row.line}-${row.product}`}>
                              <td>{row.product}</td>
                              <td className="mono">{row.sku || "—"}</td>
                              <td className="right mono">{money(row.rcv_price, rcvResult.currency)}</td>
                              <td className="right mono">
                                {money(row.catalog_cost, rcvResult.currency)}
                              </td>
                              <td className="right">
                                {row.difference_pct === null ? "—" : `${row.difference_pct}%`}
                              </td>
                              <td>
                                <span className={`badge ${row.status === "discrepancia" ? "severity-medium" : ""}`}>
                                  {labelize(row.status)}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </section>

          <aside className="stack">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Qué hace esta importación</h2>
                </div>
              </div>
              <ul className="audit-guidelist">
                <li>Reconoce RCV de documentos (folio, tipo DTE, RUT, total) y de ítems (producto, precio).</li>
                <li>Lee la tabla sin enviar tus datos a un modelo de IA.</li>
                <li>En RCV de ítems compara el costo contra tu catálogo y, si lo autorizas, actualiza solo el costo.</li>
                <li>En RCV de documentos solo previsualiza folios y montos para completitud y conciliación.</li>
                <li>Los productos nuevos entran con un margen inicial de 25%.</li>
              </ul>
              {canManage ? (
                <p className="muted small">
                  Revisa los cambios en Directorio → Catálogo antes de cotizar con los nuevos
                  costos.
                </p>
              ) : null}
            </section>
          </aside>
          </div>
        </div>
      ) : null}
    </div>
  );
}
