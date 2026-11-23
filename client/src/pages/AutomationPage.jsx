import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import { formatDate, formatDateTime, formatMoney, labelize } from "../lib/format";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import {
  AlertTriangleIcon,
  ClockIcon,
  DocumentsIcon,
  DownloadIcon,
  HistoryIcon,
  PricesIcon,
  RocketIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
  TrendUpIcon,
  UploadIcon,
} from "../components/Icons";

const AUTOMATION_STEPS = [
  { id: 1, label: "Sube o elige un documento" },
  { id: 2, label: "El pipeline corre solo" },
  { id: 3, label: "Revisa KPIs y descarga reportes" },
];

const RESULT_TABS = [
  { id: "resumen", label: "Resumen", icon: SparkIcon },
  { id: "fugas", label: "Fugas", icon: AlertTriangleIcon },
  { id: "margenes", label: "Márgenes", icon: PricesIcon },
  { id: "sii", label: "SII / RCV", icon: ShieldIcon },
  { id: "negociacion", label: "Negociación", icon: TrendUpIcon },
  { id: "agil", label: "Compra Ágil", icon: SearchIcon },
  { id: "documento", label: "Documento", icon: DocumentsIcon },
];

const STAGE_STATUS = {
  pendiente: { label: "En espera", tone: "neutral" },
  en_proceso: { label: "Ejecutando", tone: "running" },
  completado: { label: "Completado", tone: "ok" },
  fallback_ia: { label: "Fallback IA", tone: "warn" },
  sin_datos: { label: "Sin datos", tone: "neutral" },
  omitido_con_motivo: { label: "Omitido", tone: "warn" },
};

const SOURCE_LABEL = {
  internal_process: "Interno · 0 tokens",
  ai_fallback: "IA · fallback",
};

const FILE_ACCEPT = ".pdf,.xml,.dte,.xlsx,.xls,.csv,.txt,.png,.jpg,.jpeg,.webp,.tif,.tiff";

function stageStatus(status) {
  return STAGE_STATUS[status] || { label: status || "—", tone: "neutral" };
}

function metricValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "number") {
    return new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value);
}

function metricLabel(key) {
  const labels = {
    items: "Ítems",
    document_status: "Documento",
    supplier: "Proveedor",
    currency: "Moneda",
    total: "Total",
    reused: "Reutilizado",
    potential_savings: "Ahorro",
    overcost: "Sobrecosto",
    findings: "Hallazgos",
    at_risk: "En riesgo",
    below_cost: "Bajo costo",
    recovery: "Recuperación",
    rut: "RUT",
    rut_valid: "RUT válido",
    rcv_total: "Documentos RCV",
    rcv_missing: "Faltantes",
    comparisons: "Comparaciones",
    negotiation_savings: "Ahorro negociación",
    verified_savings: "Ahorro verificado",
    opportunities: "Oportunidades",
    catalog_matches: "Coincidencias",
    mode: "Modo",
    search: "Búsqueda",
  };
  return labels[key] || labelize(key);
}

function StageCard({ stage, index }) {
  const meta = stageStatus(stage.status);
  const metrics = Object.entries(stage.metrics || {}).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  return (
    <article className={`automation-stage status-${stage.status}`}>
      <div className="automation-stage-head">
        <span className="automation-stage-index">{index + 1}</span>
        <span className="automation-stage-label">{stage.label}</span>
      </div>
      <div className="automation-stage-meta">
        <span key={`${stage.id}-${stage.status}`} className={`automation-status ${meta.tone}`}>
          {meta.label}
        </span>
        {stage.source ? (
          <span className={`automation-source ${stage.source === "ai_fallback" ? "ai" : "internal"}`}>
            {SOURCE_LABEL[stage.source] || stage.source}
          </span>
        ) : null}
      </div>
      <p className="automation-stage-detail">{stage.detail || "Esperando ejecución…"}</p>
      {metrics.length ? (
        <dl className="automation-stage-metrics">
          {metrics.slice(0, 4).map(([key, value]) => (
            <div key={key}>
              <dt>{metricLabel(key)}</dt>
              <dd>{metricValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {stage.duration_ms ? (
        <small className="automation-stage-time">
          <ClockIcon /> {(stage.duration_ms / 1000).toFixed(1)} s
        </small>
      ) : null}
    </article>
  );
}

function SkeletonBlock() {
  return (
    <div className="automation-skeleton" aria-hidden="true">
      <div className="automation-skeleton-line wide" />
      <div className="automation-skeleton-grid">
        <div className="automation-skeleton-box" />
        <div className="automation-skeleton-box" />
        <div className="automation-skeleton-box" />
      </div>
      <div className="automation-skeleton-line" />
      <div className="automation-skeleton-line short" />
    </div>
  );
}

export default function AutomationPage({ onNavigate }) {
  const { user, organization, canOperate } = useAuth();
  const currency = organization?.default_currency || "CLP";

  const [run, setRun] = useState(null);
  const [history, setHistory] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [docQuery, setDocQuery] = useState("");
  const [file, setFile] = useState(null);
  const [docType, setDocType] = useState("quote");
  const [documentDate, setDocumentDate] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("resumen");
  const [flashing, setFlashing] = useState({});
  const previousKpis = useRef({});

  const canRun = canOperate || ["owner", "admin", "analyst", "user"].includes(user?.role || "");

  const loadHistory = useCallback(async () => {
    try {
      const data = await api("/api/automation/runs?limit=6");
      setHistory(data.items || []);
    } catch {
      setHistory([]);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      const data = await api("/api/documents?page_size=40");
      setDocuments(data.items || []);
    } catch {
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      const results = await Promise.allSettled([
        api("/api/automation/runs/latest"),
        api("/api/automation/runs?limit=6"),
        api("/api/documents?page_size=40"),
      ]);
      if (cancelled) return;
      if (results[0].status === "fulfilled") {
        setRun(results[0].value.run || null);
      }
      if (results[1].status === "fulfilled") {
        setHistory(results[1].value.items || []);
      }
      if (results[2].status === "fulfilled") {
        setDocuments(results[2].value.items || []);
      }
      if (results.every((result) => result.status === "rejected")) {
        setError("No se pudo cargar el estado del pipeline automático.");
      }
      setLoading(false);
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const runId = run?.id;
  const runStatus = run?.status;
  useEffect(() => {
    if (!runId || runStatus !== "running") return undefined;
    let cancelled = false;
    let timer = null;
    async function poll() {
      try {
        const data = await api(`/api/automation/runs/${runId}`);
        if (cancelled) return;
        setRun(data.run);
        if (data.run?.status === "running") {
          timer = window.setTimeout(poll, 1200);
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, 2500);
      }
    }
    timer = window.setTimeout(poll, 500);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [runId, runStatus]);

  useEffect(() => {
    if (!run || run.status === "running") return;
    loadHistory();
    loadDocuments();
  }, [run?.id, run?.status, loadHistory, loadDocuments]);

  const kpis = {
    savings: Number(run?.summary?.potential_savings || 0),
    overcost: Number(run?.summary?.overcost || 0),
    margin: Number(run?.summary?.margin_recovery || 0),
    negotiation: Number(run?.summary?.negotiation_savings || 0),
  };
  useEffect(() => {
    if (!run) return undefined;
    const next = {};
    Object.entries(kpis).forEach(([key, value]) => {
      if (previousKpis.current[key] !== undefined && previousKpis.current[key] !== value) {
        next[key] = true;
      }
      previousKpis.current[key] = value;
    });
    if (Object.keys(next).length === 0) return undefined;
    setFlashing(next);
    const timer = window.setTimeout(() => setFlashing({}), 900);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpis.savings, kpis.overcost, kpis.margin, kpis.negotiation, run?.id]);

  const filteredDocuments = documents.filter((document) => {
    const needle = docQuery.trim().toLowerCase();
    if (!needle) return true;
    return (
      String(document.original_filename || "").toLowerCase().includes(needle) ||
      String(document.supplier_name || "").toLowerCase().includes(needle)
    );
  });

  async function startExisting(documentId) {
    if (!canRun || starting) return;
    setStarting(true);
    setError("");
    setTab("resumen");
    try {
      const data = await api("/api/automation/run", {
        method: "POST",
        body: JSON.stringify({ document_id: documentId }),
      });
      setRun(data.run);
    } catch (err) {
      setError(err.message || "No se pudo iniciar el pipeline.");
    } finally {
      setStarting(false);
    }
  }

  async function startUpload() {
    if (!canRun || starting) return;
    if (!file) {
      setError("Selecciona un archivo o elige un documento existente.");
      return;
    }
    setStarting(true);
    setError("");
    setTab("resumen");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("doc_type", docType);
      if (documentDate) form.append("document_date", documentDate);
      const data = await api("/api/automation/run/upload", { method: "POST", body: form });
      setRun(data.run);
      setFile(null);
    } catch (err) {
      setError(err.message || "No se pudo iniciar el pipeline con el archivo.");
    } finally {
      setStarting(false);
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragActive(false);
    const dropped = event.dataTransfer?.files?.[0];
    if (dropped) {
      setFile(dropped);
      setError("");
    }
  }

  const stages = run?.stages || [];
  const completedInternal = stages.filter(
    (stage) => stage.status === "completado" && stage.source === "internal_process",
  ).length;
  const fallbackStages = stages.filter((stage) => stage.status === "fallback_ia");
  const aiUsed = Boolean(run?.summary?.ai_used) || fallbackStages.length > 0;
  const activeStep = !run ? 1 : run.status === "running" ? 2 : 3;
  const results = run?.results || {};
  const summary = run?.summary || {};
  const documentInfo = results.document || {};
  const audit = results.audit || {};
  const findings = audit.findings || [];
  const margin = results.margin || {};
  const marginSummary = margin.summary || {};
  const marginItems = margin.items || [];
  const siiRcv = results.sii_rcv || {};
  const rcv = siiRcv.rcv || {};
  const rut = siiRcv.rut || {};
  const comparator = results.comparator || {};
  const negotiation = results.negotiation || {};
  const savings = results.savings || {};
  const agile = results.compra_agil || {};
  const itemsPreview = results.items_preview || [];

  return (
    <div className="page-stack automation-page">
      <section className="page-intro automation-hero">
        <div className="automation-hero-copy">
          <div className="eyebrow">Automatización · Pipeline de 1 clic</div>
          <h2>Un documento entra. Todos los análisis salen.</h2>
          <p>
            Extracción, fugas, márgenes, SII/RCV, negociación y Compra Ágil en una sola corrida.
            Primero procesos internos (0 tokens de IA); la IA solo aparece como respaldo cuando
            realmente hace falta.
          </p>
          <div className="automation-pills">
            <span><SparkIcon /> Deterministic-first</span>
            <span><ShieldIcon /> Fallback controlado</span>
            <span><HistoryIcon /> Resultado persistente</span>
          </div>
        </div>
        <div className="automation-hero-stats">
          <div>
            <span>Etapas internas</span>
            <strong>{completedInternal}/6</strong>
          </div>
          <div>
            <span>Uso de IA</span>
            <strong className={aiUsed ? "warn" : "ok"}>{aiUsed ? "Fallback" : "0 tokens"}</strong>
          </div>
          <div>
            <span>Última corrida</span>
            <strong>{run ? runStatusLabel(run.status) : "Sin ejecutar"}</strong>
          </div>
        </div>
      </section>

      <QuickGuide steps={AUTOMATION_STEPS} activeStep={activeStep} />

      {error ? <div className="alert error">{error}</div> : null}

      <div className="automation-layout">
        <div className="automation-main">
          {!run ? (
            loading ? (
              <section className="card"><SkeletonBlock /></section>
            ) : (
              <section className="card automation-empty">
                <RocketIcon />
                <h3>Listo para analizar en un clic</h3>
                <p>
                  Sube una cotización, factura o lista de precios, o elige un documento ya cargado.
                  El pipeline ejecutará las seis etapas automáticamente.
                </p>
              </section>
            )
          ) : (
            <>
              <section className="automation-run-head card">
                <div>
                  <div className="automation-run-eyebrow">
                    {run.trigger_source === "upload" ? "Documento nuevo" : "Documento existente"} ·{" "}
                    {formatDateTime(run.created_at)}
                  </div>
                  <h2>{run.filename || documentInfo.filename || "Ejecución automática"}</h2>
                  <p>
                    {run.status === "running"
                      ? "El pipeline está trabajando. Cada etapa se actualiza en tiempo real."
                      : run.status === "failed"
                        ? run.error_message || "La ejecución no pudo completarse."
                        : `${summary.internal_stages ?? completedInternal} etapas internas · ${
                            summary.fallback_stages ?? fallbackStages.length
                          } fallback IA · ${summary.items ?? 0} ítems analizados.`}
                  </p>
                </div>
                <div className="automation-run-actions">
                  {documentInfo.id ? (
                    <button
                      type="button"
                      className="button ghost"
                      onClick={() =>
                        downloadFile(
                          `/api/documents/${documentInfo.id}/export?format=xlsx`,
                          "documento-procesado.xlsx",
                        )
                      }
                    >
                      <DownloadIcon /> Exportar ítems
                    </button>
                  ) : null}
                  {run.document_id ? (
                    <button
                      type="button"
                      className="button primary"
                      onClick={() => startExisting(run.document_id)}
                      disabled={starting || !canRun}
                    >
                      <RocketIcon /> {starting ? "Iniciando…" : "Reejecutar"}
                    </button>
                  ) : null}
                </div>
              </section>

              <section className="automation-kpis">
                <article className={`automation-kpi ${flashing.savings ? "flash" : ""}`}>
                  <span>Ahorro potencial</span>
                  <strong>{formatMoney(summary.potential_savings, currency)}</strong>
                  <small>{summary.findings || 0} hallazgos detectados</small>
                </article>
                <article className={`automation-kpi ${flashing.overcost ? "flash" : ""}`}>
                  <span>Sobrecostos</span>
                  <strong>{formatMoney(summary.overcost, currency)}</strong>
                  <small>Frente al mejor precio registrado</small>
                </article>
                <article className={`automation-kpi ${flashing.margin ? "flash" : ""}`}>
                  <span>Margen en riesgo</span>
                  <strong>{formatMoney(summary.margin_recovery, currency)}</strong>
                  <small>{summary.margin_at_risk || 0} productos por revisar</small>
                </article>
                <article className={`automation-kpi ${flashing.negotiation ? "flash" : ""}`}>
                  <span>Objetivo negociación</span>
                  <strong>{formatMoney(summary.negotiation_savings, currency)}</strong>
                  <small>{summary.comparisons || 0} comparaciones de precio</small>
                </article>
                <article className="automation-kpi">
                  <span>SII / RCV</span>
                  <strong>
                    {summary.sii_rcv?.total_documents
                      ? `${summary.sii_rcv.completeness_pct ?? 0}%`
                      : "Sin RCV"}
                  </strong>
                  <small>
                    {summary.sii_rcv?.missing
                      ? `${summary.sii_rcv.missing} folios sin detalle`
                      : rut.rut
                        ? `RUT ${rut.valid ? "válido" : "inválido"}`
                        : "Sin validaciones pendientes"}
                  </small>
                </article>
              </section>

              {run.status === "running" && stages.every((stage) => stage.status === "pendiente") ? (
                <section className="card"><SkeletonBlock /></section>
              ) : (
                <section className="automation-stages">
                  {stages.map((stage, index) => (
                    <StageCard key={stage.id} stage={stage} index={index} />
                  ))}
                </section>
              )}

              <div className="automation-toolbar">
                <PageTabs tabs={RESULT_TABS} active={tab} onChange={setTab} label="Resultados" />
                {run.status === "running" ? (
                  <span className="automation-live"><span /> En vivo</span>
                ) : null}
              </div>

              {tab === "resumen" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Resumen unificado</h2>
                      <p>Todo lo que encontró el pipeline, sin navegar por otras pantallas.</p>
                    </div>
                    {onNavigate ? (
                      <button
                        type="button"
                        className="button ghost"
                        onClick={() => onNavigate("audit-express")}
                      >
                        Abrir Auditoría Express
                      </button>
                    ) : null}
                  </div>
                  <div className="automation-summary-grid">
                    <div>
                      <span className="muted small">Documento</span>
                      <strong>{documentInfo.supplier_name || "Proveedor sin nombre"}</strong>
                      <p>
                        {labelize(documentInfo.doc_type)} ·{" "}
                        {documentInfo.item_count ?? itemsPreview.length} ítems
                        {documentInfo.total ? ` · ${formatMoney(documentInfo.total, currency)}` : ""}
                      </p>
                    </div>
                    <div>
                      <span className="muted small">Fugas y sobrecostos</span>
                      <strong>{formatMoney(summary.overcost, currency)}</strong>
                      <p>{summary.findings || 0} hallazgos priorizados</p>
                    </div>
                    <div>
                      <span className="muted small">Margen</span>
                      <strong>{marginSummary.at_risk ?? 0} en riesgo</strong>
                      <p>{marginSummary.below_cost ?? 0} bajo costo</p>
                    </div>
                    <div>
                      <span className="muted small">Ahorro verificado</span>
                      <strong>{formatMoney(savings.total_amount, currency)}</strong>
                      <p>{savings.count ?? 0} evidencias registradas</p>
                    </div>
                  </div>
                  <div className="automation-action-plan">
                    <strong>Plan de acción</strong>
                    {(audit.action_plan || []).length ? (
                      <ol>
                        {audit.action_plan.slice(0, 4).map((step, index) => (
                          <li key={`${step.title}-${index}`}>
                            <span>{step.title}</span>
                            <small>{step.detail}</small>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="muted small">
                        Aún no hay acciones: carga más documentos para comparar precios.
                      </p>
                    )}
                  </div>
                </section>
              ) : null}

              {tab === "fugas" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Fugas y sobrecostos</h2>
                      <p>Hallazgos de precio, margen y conciliación de facturas.</p>
                    </div>
                    <button
                      type="button"
                      className="button ghost"
                      onClick={() =>
                        downloadFile("/api/leaks/audit.pdf?days=90", "auditoria_express_nexora.pdf")
                      }
                    >
                      <DownloadIcon /> PDF
                    </button>
                  </div>
                  {findings.length ? (
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Prioridad</th>
                            <th>Hallazgo</th>
                            <th>Proveedor</th>
                            <th className="right">Ahorro est.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {findings.slice(0, 40).map((finding) => (
                            <tr key={finding.id}>
                              <td>
                                <span className={`badge severity-${finding.severity}`}>
                                  {labelize(finding.severity)}
                                </span>
                              </td>
                              <td>
                                <strong>{finding.title}</strong>
                                <div className="muted small">{finding.detail}</div>
                              </td>
                              <td>{finding.supplier || "—"}</td>
                              <td className="right mono">
                                {formatMoney(finding.savings, finding.currency || currency)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted small">Sin hallazgos con los datos actuales.</p>
                  )}
                </section>
              ) : null}

              {tab === "margenes" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Guardián de margen</h2>
                      <p>Productos con margen bajo, alza de costo o venta bajo costo.</p>
                    </div>
                    <button
                      type="button"
                      className="button ghost"
                      onClick={() =>
                        downloadFile(
                          "/api/leaks/margin-guardian.csv?only_changes=false",
                          "margen_guardian.csv",
                        )
                      }
                    >
                      <DownloadIcon /> CSV
                    </button>
                  </div>
                  {marginItems.length ? (
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Producto</th>
                            <th className="right">Costo</th>
                            <th className="right">Venta</th>
                            <th className="right">Margen</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {marginItems
                            .filter((item) => item.status !== "ok")
                            .slice(0, 40)
                            .map((item) => (
                              <tr key={item.id}>
                                <td>
                                  <strong>{item.name}</strong>
                                  <div className="muted small">{item.sku || "Sin SKU"}</div>
                                </td>
                                <td className="right mono">{formatMoney(item.cost_current, currency)}</td>
                                <td className="right mono">{formatMoney(item.sale_price, currency)}</td>
                                <td className="right">{item.margin_pct}%</td>
                                <td>
                                  <span className={`badge severity-${item.severity}`}>
                                    {item.status_label}
                                  </span>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted small">Catálogo sin productos para evaluar.</p>
                  )}
                </section>
              ) : null}

              {tab === "sii" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Validación SII / RCV</h2>
                      <p>Dígito verificador del proveedor y completitud del Registro de Compras.</p>
                    </div>
                  </div>
                  <div className="automation-sii-grid">
                    <div>
                      <span className="muted small">RUT proveedor</span>
                      <strong>{rut.rut || "Sin RUT"}</strong>
                      <p>
                        {rut.rut
                          ? rut.valid
                            ? "Formato válido (validación local del DV)."
                            : "Formato inválido: revisa el RUT del proveedor."
                          : "El documento no incluye RUT del emisor."}
                      </p>
                    </div>
                    <div>
                      <span className="muted small">Completitud RCV</span>
                      <strong>{rcv.completeness_pct ?? 0}%</strong>
                      <p>{rcv.message || "Sin período RCV para validar."}</p>
                    </div>
                  </div>
                  {(rcv.missing_documents || []).length ? (
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Folio</th>
                            <th>Proveedor</th>
                            <th className="right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rcv.missing_documents.slice(0, 30).map((row) => (
                            <tr key={`${row.tipo_doc}-${row.folio}`}>
                              <td className="mono">{row.folio}</td>
                              <td>{row.supplier || "—"}</td>
                              <td className="right mono">{formatMoney(row.total, rcv.currency)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {tab === "negociacion" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Comparador, negociación y ahorro</h2>
                      <p>
                        Alternativas de precio, objetivo de negociación y evidencias de ahorro.
                      </p>
                    </div>
                    <div className="card-head-tools">
                      <button
                        type="button"
                        className="button ghost small"
                        onClick={() =>
                          downloadFile("/api/insights/savings/verified.pdf", "ahorro_verificado.pdf")
                        }
                      >
                        <DownloadIcon /> PDF ahorro
                      </button>
                      <button
                        type="button"
                        className="button ghost small"
                        onClick={() =>
                          downloadFile("/api/insights/savings/verified.csv", "ahorro_verificado.csv")
                        }
                      >
                        <DownloadIcon /> CSV ahorro
                      </button>
                    </div>
                  </div>
                  {(negotiation.suppliers || []).length ? (
                    <div className="automation-negotiation">
                      {negotiation.suppliers.map((supplier) => (
                        <div key={supplier.supplier} className="automation-negotiation-row">
                          <div>
                            <strong>{supplier.supplier}</strong>
                            <div className="muted small">
                              {supplier.items.length} productos · objetivo{" "}
                              {formatMoney(supplier.target_total, negotiation.currency)}
                            </div>
                          </div>
                          <div className="automation-negotiation-saving">
                            <span className="muted small">Ahorro estimado</span>
                            <strong>{formatMoney(supplier.estimated_savings, negotiation.currency)}</strong>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted small">
                      Sin brechas suficientes. Necesitas al menos dos proveedores con precios del
                      mismo producto.
                    </p>
                  )}
                  <div className="automation-summary-grid">
                    <div>
                      <span className="muted small">Comparaciones</span>
                      <strong>{comparator.total ?? 0}</strong>
                    </div>
                    <div>
                      <span className="muted small">Ahorro negociación</span>
                      <strong>{formatMoney(negotiation.total_estimated_savings, currency)}</strong>
                    </div>
                    <div>
                      <span className="muted small">Ahorro verificado</span>
                      <strong>{formatMoney(savings.total_amount, currency)}</strong>
                    </div>
                    <div>
                      <span className="muted small">Evidencias</span>
                      <strong>{savings.count ?? 0}</strong>
                    </div>
                  </div>
                </section>
              ) : null}

              {tab === "agil" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Compra Ágil y oportunidades</h2>
                      <p>Referencias externas y coincidencias con tu catálogo de precios.</p>
                    </div>
                    {onNavigate ? (
                      <button
                        type="button"
                        className="button ghost"
                        onClick={() => onNavigate("compra-agil")}
                      >
                        Abrir radar
                      </button>
                    ) : null}
                  </div>
                  {(agile.opportunities || []).length ? (
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Oportunidad</th>
                            <th>Comprador</th>
                            <th className="right">Presupuesto</th>
                          </tr>
                        </thead>
                        <tbody>
                          {agile.opportunities.map((row) => (
                            <tr key={row.external_id}>
                              <td>
                                <strong>{row.title}</strong>
                                <div className="muted small">{row.external_id}</div>
                              </td>
                              <td>{row.buyer || "—"}</td>
                              <td className="right mono">{formatMoney(row.budget_clp, currency)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted small">{agile.message || "Sin oportunidades externas."}</p>
                  )}
                  {(agile.catalog_matches || []).length ? (
                    <>
                      <h3 className="automation-subtitle">Coincidencias en tu catálogo</h3>
                      <div className="table-wrap">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Producto</th>
                              <th>Proveedor</th>
                              <th className="right">Mejor precio</th>
                            </tr>
                          </thead>
                          <tbody>
                            {agile.catalog_matches.map((row, index) => (
                              <tr key={`${row.sku || row.product}-${index}`}>
                                <td>{row.product}</td>
                                <td>{row.supplier || "—"}</td>
                                <td className="right mono">{formatMoney(row.price, currency)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : null}
                </section>
              ) : null}

              {tab === "documento" ? (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <h2>Documento y extracción</h2>
                      <p>Ítems normalizados y trazabilidad del origen de extracción.</p>
                    </div>
                    <div className="card-head-tools">
                      {documentInfo.id ? (
                        <>
                          <button
                            type="button"
                            className="button ghost small"
                            onClick={() =>
                              downloadFile(
                                `/api/documents/${documentInfo.id}/export?format=xlsx`,
                                "documento-procesado.xlsx",
                              )
                            }
                          >
                            <DownloadIcon /> Excel
                          </button>
                          <button
                            type="button"
                            className="button ghost small"
                            onClick={() =>
                              downloadFile(
                                `/api/documents/${documentInfo.id}/export?format=pdf`,
                                "documento-procesado.pdf",
                              )
                            }
                          >
                            <DownloadIcon /> PDF
                          </button>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <div className="automation-doc-meta">
                    <span><strong>Archivo:</strong> {documentInfo.filename || "—"}</span>
                    <span><strong>Estado:</strong> {labelize(documentInfo.status)}</span>
                    <span><strong>Proveedor:</strong> {documentInfo.supplier_name || "—"}</span>
                    <span><strong>Origen:</strong> {labelize(documentInfo.extraction_provider) || "—"}</span>
                    <span><strong>IA:</strong> {documentInfo.ai_used ? "Fallback usado" : "No usada"}</span>
                  </div>
                  {itemsPreview.length ? (
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>SKU</th>
                            <th>Descripción</th>
                            <th className="right">Cantidad</th>
                            <th className="right">Precio normalizado</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {itemsPreview.slice(0, 60).map((item, index) => (
                            <tr key={`${item.sku || item.description}-${index}`}>
                              <td className="mono">{item.sku || "—"}</td>
                              <td>{item.description}</td>
                              <td className="right">{metricValue(item.quantity)}</td>
                              <td className="right mono">
                                {formatMoney(item.normalized_unit_price, item.currency || currency)}
                              </td>
                              <td>
                                <span className="badge">{labelize(item.review_status)}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted small">Sin ítems extraídos para este documento.</p>
                  )}
                </section>
              ) : null}
            </>
          )}
        </div>

        <aside className="automation-side">
          <section className="card automation-launch">
            <div className="card-head">
              <div>
                <h2>Ejecutar pipeline</h2>
                <p>Sube un archivo o elige uno ya cargado.</p>
              </div>
            </div>
            <div
              className={`automation-drop ${dragActive ? "drag" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
            >
              <UploadIcon />
              <strong>{file ? file.name : "Arrastra tu documento aquí"}</strong>
              <span>PDF, XML/DTE, Excel, CSV o imagen · máx. 25 MB</span>
              <label className="button ghost small automation-file-button">
                <input
                  type="file"
                  accept={FILE_ACCEPT}
                  onChange={(event) => {
                    setFile(event.target.files?.[0] || null);
                    setError("");
                  }}
                />
                Seleccionar archivo
              </label>
            </div>
            <div className="automation-form-row">
              <label>
                <span>Tipo</span>
                <select value={docType} onChange={(event) => setDocType(event.target.value)}>
                  <option value="quote">Cotización</option>
                  <option value="invoice">Factura</option>
                  <option value="price_list">Lista de precios</option>
                </select>
              </label>
              <label>
                <span>Fecha del documento</span>
                <input
                  type="date"
                  value={documentDate}
                  onChange={(event) => setDocumentDate(event.target.value)}
                />
              </label>
            </div>
            <button
              type="button"
              className="button primary automation-run-button"
              onClick={startUpload}
              disabled={!file || starting || !canRun}
            >
              <RocketIcon /> {starting ? "Ejecutando…" : "Ejecutar pipeline automático"}
            </button>
            {!canRun ? (
              <p className="muted small">Tu rol puede revisar resultados, pero no ejecutar el pipeline.</p>
            ) : null}
          </section>

          <section className="card automation-documents">
            <div className="card-head">
              <div>
                <h2>Documentos cargados</h2>
                <p>Un clic para reutilizar y analizar.</p>
              </div>
              <span className="badge">{filteredDocuments.length}</span>
            </div>
            <label className="search-field">
              <SearchIcon />
              <input
                value={docQuery}
                onChange={(event) => setDocQuery(event.target.value)}
                placeholder="Buscar por archivo o proveedor"
              />
            </label>
            <div className="automation-doc-list">
              {filteredDocuments.length ? (
                filteredDocuments.slice(0, 12).map((document) => (
                  <button
                    key={document.id}
                    type="button"
                    className="automation-doc-item"
                    onClick={() => startExisting(document.id)}
                    disabled={starting || !canRun}
                  >
                    <span className={`automation-doc-dot ${document.status}`} />
                    <span className="automation-doc-copy">
                      <strong>{document.original_filename}</strong>
                      <small>
                        {document.supplier_name || "Sin proveedor"} ·{" "}
                        {formatDate(document.created_at)}
                      </small>
                    </span>
                    <span className={`badge status-${document.status}`}>
                      {labelize(document.status)}
                    </span>
                  </button>
                ))
              ) : (
                <p className="muted small">Aún no hay documentos. Sube el primero arriba.</p>
              )}
            </div>
          </section>

          <section className="card automation-history">
            <div className="card-head">
              <div>
                <h2>Historial automático</h2>
                <p>Resultados persistidos de las últimas corridas.</p>
              </div>
            </div>
            {history.length ? (
              <div className="automation-history-list">
                {history.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`automation-history-item ${run?.id === item.id ? "active" : ""}`}
                    onClick={async () => {
                      try {
                        const data = await api(`/api/automation/runs/${item.id}`);
                        setRun(data.run);
                        setTab("resumen");
                      } catch {
                        setError("No se pudo abrir esa ejecución.");
                      }
                    }}
                  >
                    <span className={`automation-doc-dot ${item.status}`} />
                    <span>
                      <strong>{item.filename || "Ejecución"}</strong>
                      <small>{formatDateTime(item.created_at)}</small>
                    </span>
                    <span className={`badge status-${item.status}`}>{runStatusLabel(item.status)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted small">Todavía no hay ejecuciones guardadas.</p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function runStatusLabel(status) {
  return {
    running: "En proceso",
    completed: "Completada",
    failed: "Fallida",
  }[status] || status || "—";
}
