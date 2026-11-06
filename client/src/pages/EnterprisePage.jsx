import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import { formatDate, formatDateTime, formatMoney, formatNumber, labelize } from "../lib/format";
import {
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  DownloadIcon,
  InfoIcon,
  PlusIcon,
  ShieldIcon,
  SparkIcon,
  TrashIcon,
} from "../components/Icons";

const CURRENCIES = ["CLP", "USD", "EUR", "PEN", "COP", "MXN", "BRL", "ARS"];

const TABS = [
  { id: "roi", label: "ROI ejecutivo", icon: SparkIcon },
  { id: "scorecards", label: "Proveedores", icon: CheckIcon },
  { id: "alerts", label: "Alertas", icon: BellIcon },
  { id: "integrations", label: "Integraciones", icon: ArrowRightIcon },
  { id: "security", label: "Seguridad y push", icon: ShieldIcon },
  { id: "branding", label: "White-label", icon: SparkIcon },
  { id: "onboarding", label: "Onboarding", icon: CheckIcon },
];

const STEP_TARGETS = {
  branding: { tab: "branding" },
  documents: { page: "documents" },
  suppliers: { page: "suppliers" },
  team: { page: "team" },
  integrations: { tab: "integrations" },
  approvals: { page: "approvals" },
  notifications: { tab: "alerts" },
  pwa: { tab: "security" },
};

function Metric({ label, value, detail, tone = "" }) {
  return (
    <div className={`enterprise-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function SectionHead({ title, description, children }) {
  return (
    <div className="card-head">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {children ? <div className="card-head-tools">{children}</div> : null}
    </div>
  );
}

function useCurrency(defaultCurrency) {
  const [currency, setCurrency] = useState(defaultCurrency || "CLP");
  useEffect(() => {
    if (defaultCurrency && !currency) setCurrency(defaultCurrency);
  }, [defaultCurrency, currency]);
  return [currency, setCurrency];
}

function RoiTab() {
  const { organization } = useAuth();
  const [currency, setCurrency] = useCurrency(organization?.default_currency);
  const [roi, setRoi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api(`/api/enterprise/roi?currency=${encodeURIComponent(currency)}&months=6`)
      .then((data) => {
        if (!cancelled) {
          setRoi(data);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "No se pudo cargar el ROI.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currency]);

  async function exportReport(format) {
    try {
      await downloadFile(
        `/api/enterprise/roi/export?format=${format}&currency=${encodeURIComponent(currency)}&months=6`,
        `nexora-roi.${format}`,
      );
    } catch (err) {
      setError(err.message || "No se pudo exportar el reporte.");
    }
  }

  return (
    <div className="stack">
      {error ? <div className="alert error">{error}</div> : null}
      <section className="card">
        <SectionHead
          title="Reporte ejecutivo de ROI"
          description="Ahorro capturado, exposición pendiente y eficiencia operativa de los últimos 6 meses."
        >
          <label className="page-size">
            <span>Moneda</span>
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              {CURRENCIES.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <button type="button" className="button ghost small" onClick={() => exportReport("xlsx")}>
            <DownloadIcon /> Excel
          </button>
          <button type="button" className="button primary small" onClick={() => exportReport("pdf")}>
            <DownloadIcon /> PDF
          </button>
        </SectionHead>

        {loading ? (
          <div className="empty-state">Calculando ROI…</div>
        ) : roi ? (
          <>
            <div className="enterprise-metrics">
              <Metric
                label="Compra auditada"
                value={formatMoney(roi.audited_spend, currency)}
                detail={`${roi.documents} documentos · ${roi.items} ítems`}
              />
              <Metric
                label="Ahorro estimado"
                value={formatMoney(roi.estimated_savings, currency)}
                detail={`${formatNumber(roi.savings_rate_pct, 2)}% de la compra auditada`}
                tone="ok"
              />
              <Metric
                label="Exposición pendiente"
                value={formatMoney(roi.potential_exposure, currency)}
                detail={`${roi.pending_exceptions} alertas por resolver`}
                tone="warning"
              />
              <Metric
                label="Horas manuales ahorradas"
                value={formatNumber(roi.manual_hours_saved, 1)}
                detail="Estimación operativa del período"
              />
            </div>
            <p className="enterprise-note">
              <InfoIcon /> El ahorro se estima comparando precios auditados contra la mediana histórica
              de las alzas aprobadas o resueltas. Las horas ahorradas usan supuestos configurables del producto.
            </p>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mes</th>
                    <th>Compra auditada</th>
                    <th>Ahorro capturado</th>
                    <th>Alertas de alza</th>
                    <th>Documentos</th>
                  </tr>
                </thead>
                <tbody>
                  {(roi.monthly || []).map((row) => (
                    <tr key={row.month}>
                      <td>{row.month}</td>
                      <td className="mono">{formatMoney(row.spend, currency)}</td>
                      <td className="mono">{formatMoney(row.savings, currency)}</td>
                      <td>{row.price_alerts}</td>
                      <td>{row.documents}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}

function ScorecardsTab() {
  const { organization } = useAuth();
  const [currency, setCurrency] = useCurrency(organization?.default_currency);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api(`/api/enterprise/suppliers/scorecards?currency=${encodeURIComponent(currency)}`)
      .then((data) => {
        if (!cancelled) {
          setItems(data.items || []);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "No se pudieron cargar los scorecards.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currency]);

  return (
    <section className="card">
      <SectionHead
        title="Scorecard de proveedores"
        description="Ranking por confianza, incidencias y ahorro capturado."
      >
        <label className="page-size">
          <span>Moneda</span>
          <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
            {CURRENCIES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
      </SectionHead>
      {error ? <div className="alert error">{error}</div> : null}
      {loading ? (
        <div className="empty-state">Calculando scorecards…</div>
      ) : items.length === 0 ? (
        <div className="empty-state">Aún no hay proveedores con actividad auditada.</div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Proveedor</th>
                <th>Score</th>
                <th>Compra</th>
                <th>Ahorro</th>
                <th>Docs</th>
                <th>Ítems</th>
                <th>Excepciones</th>
                <th>Confianza</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id}>
                  <td>{row.rank}</td>
                  <td><strong>{row.name}</strong></td>
                  <td>
                    <span className={`score-badge ${row.score >= 80 ? "good" : row.score >= 60 ? "mid" : "low"}`}>
                      {row.score}
                    </span>
                  </td>
                  <td className="mono">{formatMoney(row.spend, currency)}</td>
                  <td className="mono">{formatMoney(row.savings, currency)}</td>
                  <td>{row.documents}</td>
                  <td>{row.items}</td>
                  <td>{row.pending_exceptions} / {row.total_exceptions}</td>
                  <td>{formatNumber(row.avg_confidence * 100, 1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AlertsTab() {
  const { organization } = useAuth();
  const [currency] = useCurrency(organization?.default_currency);
  const [alerts, setAlerts] = useState([]);
  const [channels, setChannels] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [form, setForm] = useState({ name: "", channel: "email", target: "", events: "alerts" });
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [alertData, channelData, deliveryData] = await Promise.all([
        api(`/api/enterprise/alerts?currency=${encodeURIComponent(currency)}`),
        api("/api/enterprise/notifications/channels"),
        api("/api/enterprise/notifications/deliveries?limit=20"),
      ]);
      setAlerts(alertData.items || []);
      setChannels(channelData.items || []);
      setDeliveries(deliveryData.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudieron cargar las alertas.");
    } finally {
      setLoading(false);
    }
  }, [currency]);

  useEffect(() => {
    load();
  }, [load]);

  async function createChannel(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api("/api/enterprise/notifications/channels", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          channel: form.channel,
          target: form.target,
          events: form.events.split(",").map((value) => value.trim()).filter(Boolean),
        }),
      });
      setSuccess("Canal de alertas creado.");
      setForm({ name: "", channel: "email", target: "", events: "alerts" });
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear el canal.");
    } finally {
      setPending(false);
    }
  }

  async function dispatch() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const result = await api("/api/enterprise/notifications/dispatch", { method: "POST", body: "{}" });
      setSuccess(`Alertas despachadas a ${result.deliveries.length} canal(es).`);
      load();
    } catch (err) {
      setError(err.message || "No se pudieron despachar las alertas.");
    } finally {
      setPending(false);
    }
  }

  async function testChannel(channel) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api(`/api/enterprise/notifications/channels/${channel.id}/test`, { method: "POST", body: "{}" });
      setSuccess(`Prueba enviada a ${channel.name}.`);
      load();
    } catch (err) {
      setError(err.message || "No se pudo probar el canal.");
    } finally {
      setPending(false);
    }
  }

  async function removeChannel(channel) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api(`/api/enterprise/notifications/channels/${channel.id}`, { method: "DELETE" });
      setSuccess("Canal eliminado.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar el canal.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <section className="card">
        <SectionHead
          title="Alertas proactivas"
          description="Notifica excepciones críticas, alzas y aprobaciones pendientes por email, Slack, WhatsApp o webhook."
        >
          <button type="button" className="button primary small" onClick={dispatch} disabled={pending}>
            <BellIcon /> Despachar ahora
          </button>
        </SectionHead>
        <div className="alert-list">
          {loading ? (
            <div className="empty-state">Cargando alertas…</div>
          ) : alerts.map((alert) => (
            <div key={alert.id} className={`alert-card ${alert.tone || ""}`}>
              <strong>{alert.title}</strong>
              <span>{alert.body}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <SectionHead title="Canales" description="Configura destinos por tipo de evento." />
        <form className="enterprise-inline-form" onSubmit={createChannel}>
          <label className="form-field">
            <span>Nombre</span>
            <input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Compras"
              required
            />
          </label>
          <label className="form-field">
            <span>Tipo</span>
            <select
              value={form.channel}
              onChange={(event) => setForm((current) => ({ ...current, channel: event.target.value }))}
            >
              <option value="email">Email</option>
              <option value="slack">Slack</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="webhook">Webhook</option>
            </select>
          </label>
          <label className="form-field grow">
            <span>Destino</span>
            <input
              value={form.target}
              onChange={(event) => setForm((current) => ({ ...current, target: event.target.value }))}
              placeholder="compras@empresa.cl o URL del webhook"
              required
            />
          </label>
          <label className="form-field">
            <span>Eventos</span>
            <input
              value={form.events}
              onChange={(event) => setForm((current) => ({ ...current, events: event.target.value }))}
              placeholder="alerts"
            />
          </label>
          <button type="submit" className="button primary" disabled={pending}>
            <PlusIcon /> Agregar
          </button>
        </form>

        {channels.length === 0 ? (
          <div className="empty-state">No hay canales configurados.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Destino</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {channels.map((channel) => (
                  <tr key={channel.id}>
                    <td>{channel.name}</td>
                    <td><span className="badge">{labelize(channel.channel)}</span></td>
                    <td className="mono">{channel.target}</td>
                    <td>{channel.active ? "Activo" : "Inactivo"}</td>
                    <td>
                      <div className="table-actions">
                        <button type="button" className="button ghost small" onClick={() => testChannel(channel)} disabled={pending}>
                          Probar
                        </button>
                        <button type="button" className="button ghost small danger" onClick={() => removeChannel(channel)} disabled={pending}>
                          <TrashIcon />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <SectionHead title="Últimas entregas" description="Trazabilidad de alertas enviadas." />
        {deliveries.length === 0 ? (
          <div className="empty-state">Sin entregas registradas.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Canal</th>
                  <th>Evento</th>
                  <th>Destino</th>
                  <th>Estado</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((delivery) => (
                  <tr key={delivery.id}>
                    <td>{formatDateTime(delivery.created_at)}</td>
                    <td>{delivery.channel_name || "—"}</td>
                    <td>{delivery.event_type}</td>
                    <td className="mono">{delivery.recipient || "—"}</td>
                    <td><span className="badge">{labelize(delivery.status)}</span></td>
                    <td>{delivery.error || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function IntegrationsTab() {
  const [integrations, setIntegrations] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [webhooks, setWebhooks] = useState([]);
  const [inbound, setInbound] = useState([]);
  const [integrationForm, setIntegrationForm] = useState({ provider: "erp", name: "", endpoint: "" });
  const [apiKeyName, setApiKeyName] = useState("");
  const [webhookForm, setWebhookForm] = useState({ url: "" });
  const [newApiKey, setNewApiKey] = useState("");
  const [newWebhookSecret, setNewWebhookSecret] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      const [integrationData, apiKeyData, webhookData, inboundData] = await Promise.all([
        api("/api/enterprise/integrations"),
        api("/api/enterprise/api-keys"),
        api("/api/enterprise/webhooks"),
        api("/api/enterprise/inbound-email/tokens"),
      ]);
      setIntegrations(integrationData.items || []);
      setApiKeys(apiKeyData.items || []);
      setWebhooks(webhookData.items || []);
      setInbound(inboundData.items || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las integraciones.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createIntegration(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api("/api/enterprise/integrations", {
        method: "POST",
        body: JSON.stringify({
          provider: integrationForm.provider,
          name: integrationForm.name,
          config: integrationForm.endpoint ? { endpoint: integrationForm.endpoint } : {},
        }),
      });
      setSuccess("Integración creada.");
      setIntegrationForm({ provider: "erp", name: "", endpoint: "" });
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear la integración.");
    } finally {
      setPending(false);
    }
  }

  async function syncIntegration(integration) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const result = await api(`/api/enterprise/integrations/${integration.id}/sync`, { method: "POST", body: "{}" });
      setSuccess(result.detail || "Sincronización ejecutada.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo sincronizar.");
    } finally {
      setPending(false);
    }
  }

  async function removeIntegration(integration) {
    setPending(true);
    try {
      await api(`/api/enterprise/integrations/${integration.id}`, { method: "DELETE" });
      setSuccess("Integración eliminada.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar.");
    } finally {
      setPending(false);
    }
  }

  async function createApiKey(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: apiKeyName, scopes: ["read"] }),
      });
      setNewApiKey(data.token);
      setApiKeyName("");
      setSuccess("API key creada. Cópiala ahora: no se volverá a mostrar.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear la API key.");
    } finally {
      setPending(false);
    }
  }

  async function revokeApiKey(key) {
    setPending(true);
    try {
      await api(`/api/enterprise/api-keys/${key.id}`, { method: "DELETE" });
      setSuccess("API key revocada.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo revocar.");
    } finally {
      setPending(false);
    }
  }

  async function createWebhook(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/webhooks", {
        method: "POST",
        body: JSON.stringify({ url: webhookForm.url, events: ["document.processed", "approval.pending"] }),
      });
      setNewWebhookSecret(data.secret);
      setWebhookForm({ url: "" });
      setSuccess("Webhook creado.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear el webhook.");
    } finally {
      setPending(false);
    }
  }

  async function testWebhook(webhook) {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await api(`/api/enterprise/webhooks/${webhook.id}/test`, { method: "POST", body: "{}" });
      setSuccess("Webhook entregado correctamente.");
    } catch (err) {
      setError(err.message || "No se pudo entregar el webhook.");
    } finally {
      setPending(false);
    }
  }

  async function removeWebhook(webhook) {
    setPending(true);
    try {
      await api(`/api/enterprise/webhooks/${webhook.id}`, { method: "DELETE" });
      setSuccess("Webhook eliminado.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar.");
    } finally {
      setPending(false);
    }
  }

  async function createInboundToken() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/inbound-email/tokens", {
        method: "POST",
        body: JSON.stringify({ label: "Ingesta" }),
      });
      setSuccess(`Dirección creada: ${data.address}`);
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear la dirección.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <section className="card">
        <SectionHead title="Integraciones" description="ERP, SII, ChileCompra y conectores genéricos." />
        <form className="enterprise-inline-form" onSubmit={createIntegration}>
          <label className="form-field">
            <span>Proveedor</span>
            <select
              value={integrationForm.provider}
              onChange={(event) => setIntegrationForm((current) => ({ ...current, provider: event.target.value }))}
            >
              <option value="erp">ERP</option>
              <option value="sii">SII</option>
              <option value="chilecompra">ChileCompra</option>
              <option value="slack">Slack</option>
              <option value="webhook">Webhook</option>
              <option value="google_workspace">Google Workspace</option>
            </select>
          </label>
          <label className="form-field">
            <span>Nombre</span>
            <input
              value={integrationForm.name}
              onChange={(event) => setIntegrationForm((current) => ({ ...current, name: event.target.value }))}
              required
            />
          </label>
          <label className="form-field grow">
            <span>Endpoint de prueba (opcional)</span>
            <input
              value={integrationForm.endpoint}
              onChange={(event) => setIntegrationForm((current) => ({ ...current, endpoint: event.target.value }))}
              placeholder="https://api.erp.cl/health"
            />
          </label>
          <button type="submit" className="button primary" disabled={pending}>
            <PlusIcon /> Conectar
          </button>
        </form>
        {integrations.length === 0 ? (
          <div className="empty-state">Sin integraciones configuradas.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Proveedor</th>
                  <th>Estado</th>
                  <th>Última sync</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {integrations.map((integration) => (
                  <tr key={integration.id}>
                    <td>{integration.name}</td>
                    <td><span className="badge">{labelize(integration.provider)}</span></td>
                    <td>{integration.last_sync_status || (integration.active ? "Activa" : "Inactiva")}</td>
                    <td>{integration.last_sync_at ? formatDateTime(integration.last_sync_at) : "—"}</td>
                    <td>
                      <div className="table-actions">
                        <button type="button" className="button ghost small" onClick={() => syncIntegration(integration)} disabled={pending}>
                          Sincronizar
                        </button>
                        <button type="button" className="button ghost small danger" onClick={() => removeIntegration(integration)} disabled={pending}>
                          <TrashIcon />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <SectionHead
          title="API pública"
          description="Usa X-API-Key para consultar /api/public/v1/summary, /items, /suppliers y /approvals."
        />
        <form className="enterprise-inline-form" onSubmit={createApiKey}>
          <label className="form-field grow">
            <span>Nombre de la key</span>
            <input value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} required />
          </label>
          <button type="submit" className="button primary" disabled={pending}>
            <PlusIcon /> Crear API key
          </button>
        </form>
        {newApiKey ? (
          <div className="secret-box">
            <span>Nueva API key (solo se muestra una vez)</span>
            <code>{newApiKey}</code>
          </div>
        ) : null}
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Prefijo</th>
                <th>Último uso</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td className="mono">{key.key_prefix}…</td>
                  <td>{key.last_used_at ? formatDateTime(key.last_used_at) : "—"}</td>
                  <td>{key.active ? "Activa" : "Revocada"}</td>
                  <td>
                    {key.active ? (
                      <button type="button" className="button ghost small danger" onClick={() => revokeApiKey(key)} disabled={pending}>
                        Revocar
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <SectionHead title="Webhooks salientes" description="Recibe eventos con firma HMAC SHA-256." />
        <form className="enterprise-inline-form" onSubmit={createWebhook}>
          <label className="form-field grow">
            <span>URL del webhook</span>
            <input
              value={webhookForm.url}
              onChange={(event) => setWebhookForm({ url: event.target.value })}
              placeholder="https://tu-sistema.cl/nexora/webhook"
              required
            />
          </label>
          <button type="submit" className="button primary" disabled={pending}>
            <PlusIcon /> Crear webhook
          </button>
        </form>
        {newWebhookSecret ? (
          <div className="secret-box">
            <span>Secreto de firma</span>
            <code>{newWebhookSecret}</code>
          </div>
        ) : null}
        {webhooks.length === 0 ? (
          <div className="empty-state">Sin webhooks configurados.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>URL</th>
                  <th>Eventos</th>
                  <th>Última entrega</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((webhook) => (
                  <tr key={webhook.id}>
                    <td className="mono">{webhook.url}</td>
                    <td>{(webhook.events || []).join(", ")}</td>
                    <td>{webhook.last_delivery_at ? formatDateTime(webhook.last_delivery_at) : "—"}</td>
                    <td>
                      <div className="table-actions">
                        <button type="button" className="button ghost small" onClick={() => testWebhook(webhook)} disabled={pending}>
                          Probar
                        </button>
                        <button type="button" className="button ghost small danger" onClick={() => removeWebhook(webhook)} disabled={pending}>
                          <TrashIcon />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <SectionHead
          title="Ingesta automática por email"
          description="Reenvía cotizaciones o facturas a una dirección dedicada."
        >
          <button type="button" className="button primary small" onClick={createInboundToken} disabled={pending}>
            <PlusIcon /> Nueva dirección
          </button>
        </SectionHead>
        {inbound.length === 0 ? (
          <div className="empty-state">Sin direcciones de ingesta.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dirección</th>
                  <th>Estado</th>
                  <th>Último email</th>
                  <th>Creada</th>
                </tr>
              </thead>
              <tbody>
                {inbound.map((token) => (
                  <tr key={token.id}>
                    <td className="mono">{token.address}</td>
                    <td>{token.active ? "Activa" : "Inactiva"}</td>
                    <td>{token.last_received_at ? formatDateTime(token.last_received_at) : "—"}</td>
                    <td>{formatDate(token.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

function SecurityTab() {
  const { user } = useAuth();
  const [security, setSecurity] = useState(null);
  const [push, setPush] = useState({ enabled: false, public_key: "" });
  const [form, setForm] = useState({ sso_enabled: false, sso_domain: "", sso_required: false, audit_retention_days: 365 });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      const [securityData, pushData] = await Promise.all([
        api("/api/enterprise/security"),
        api("/api/enterprise/push/public-key"),
      ]);
      setSecurity(securityData);
      setPush(pushData);
      setForm({
        sso_enabled: securityData.sso_enabled,
        sso_domain: securityData.sso_domain,
        sso_required: securityData.sso_required,
        audit_retention_days: securityData.audit_retention_days,
      });
    } catch (err) {
      setError(err.message || "No se pudo cargar seguridad.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function saveSecurity(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/security", {
        method: "PATCH",
        body: JSON.stringify({
          ...form,
          audit_retention_days: Number(form.audit_retention_days),
        }),
      });
      setSecurity((current) => ({ ...current, ...data }));
      setSuccess("Configuración de seguridad guardada.");
    } catch (err) {
      setError(err.message || "No se pudo guardar.");
    } finally {
      setPending(false);
    }
  }

  async function purgeAudit() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/security/purge-audit", { method: "POST", body: "{}" });
      setSuccess(`Auditoría depurada: ${data.deleted} evento(s) eliminados.`);
      load();
    } catch (err) {
      setError(err.message || "No se pudo depurar.");
    } finally {
      setPending(false);
    }
  }

  async function enablePush() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      if (!("Notification" in window)) {
        throw new Error("Este navegador no soporta notificaciones.");
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error("Permiso de notificaciones denegado.");
      }
      if (!push.enabled) {
        new Notification("NEXORA", { body: "Notificaciones locales activadas en este dispositivo." });
        setSuccess("Notificaciones locales activadas. Configura VAPID para push en segundo plano.");
        return;
      }
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        throw new Error("Este navegador no soporta Web Push.");
      }
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(push.public_key),
      });
      const json = subscription.toJSON();
      await api("/api/enterprise/push/subscribe", {
        method: "POST",
        body: JSON.stringify({
          endpoint: json.endpoint,
          p256dh: json.keys.p256dh,
          auth: json.keys.auth,
        }),
      });
      setSuccess("Push registrado para este dispositivo.");
    } catch (err) {
      setError(err.message || "No se pudo activar push.");
    } finally {
      setPending(false);
    }
  }

  async function testPush() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/push/test", { method: "POST", body: "{}" });
      setSuccess(data.configured ? `Push enviado a ${data.sent} dispositivo(s).` : (data.detail || "Push no configurado."));
    } catch (err) {
      setError(err.message || "No se pudo enviar push.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <section className="card">
        <SectionHead
          title="SSO y auditoría avanzada"
          description="Restringe el acceso por dominio Google Workspace y define retención de auditoría."
        />
        <form onSubmit={saveSecurity}>
          <div className="form-grid">
            <label className="form-field checkbox-field">
              <input
                type="checkbox"
                checked={form.sso_enabled}
                onChange={(event) => setForm((current) => ({ ...current, sso_enabled: event.target.checked }))}
              />
              <span>Habilitar SSO con Google Workspace</span>
            </label>
            <label className="form-field checkbox-field">
              <input
                type="checkbox"
                checked={form.sso_required}
                onChange={(event) => setForm((current) => ({ ...current, sso_required: event.target.checked }))}
              />
              <span>Exigir SSO (bloquea contraseña)</span>
            </label>
            <label className="form-field">
              <span>Dominio autorizado</span>
              <input
                value={form.sso_domain}
                onChange={(event) => setForm((current) => ({ ...current, sso_domain: event.target.value }))}
                placeholder="empresa.cl"
              />
            </label>
            <label className="form-field">
              <span>Retención de auditoría (días)</span>
              <input
                type="number"
                min="30"
                max="3650"
                value={form.audit_retention_days}
                onChange={(event) => setForm((current) => ({ ...current, audit_retention_days: event.target.value }))}
              />
            </label>
          </div>
          <div className="form-actions">
            <button type="button" className="button ghost" onClick={purgeAudit} disabled={pending}>
              Depurar auditoría antigua
            </button>
            <button type="submit" className="button primary" disabled={pending}>
              Guardar seguridad
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <SectionHead
          title="Notificaciones PWA"
          description={push.enabled ? "Web Push con VAPID configurado." : "Modo local: activa notificaciones del navegador."}
        >
          <button type="button" className="button primary small" onClick={enablePush} disabled={pending}>
            <BellIcon /> Activar en este dispositivo
          </button>
          <button type="button" className="button ghost small" onClick={testPush} disabled={pending}>
            Enviar prueba
          </button>
        </SectionHead>
        <p className="muted">
          Usuario actual: {user?.email}. {security?.audit_events ?? 0} evento(s) de auditoría disponibles.
        </p>
      </section>

      <section className="card">
        <SectionHead title="Sesiones recientes" description="Últimos accesos registrados para la organización." />
        {!security?.sessions?.length ? (
          <div className="empty-state">Sin sesiones registradas.</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Usuario</th>
                  <th>IP</th>
                  <th>Dispositivo</th>
                </tr>
              </thead>
              <tbody>
                {security.sessions.map((session) => (
                  <tr key={session.id}>
                    <td>{formatDateTime(session.created_at)}</td>
                    <td>{session.user_name || session.user_email}</td>
                    <td className="mono">{session.ip_address || "—"}</td>
                    <td className="truncate">{session.user_agent || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function BrandingTab() {
  const { applyBranding } = useAuth();
  const [form, setForm] = useState({
    brand_name: "",
    brand_primary_color: "#10b981",
    brand_accent_color: "#059669",
    logo_url: "",
    support_email: "",
    custom_domain: "",
    hide_powered_by: false,
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api("/api/enterprise/branding")
      .then((data) => setForm((current) => ({ ...current, ...data })))
      .catch((err) => setError(err.message || "No se pudo cargar la marca."));
  }, []);

  async function saveBranding(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/enterprise/branding", {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      setForm((current) => ({ ...current, ...data }));
      applyBranding(data);
      setSuccess("Marca actualizada.");
    } catch (err) {
      setError(err.message || "No se pudo guardar la marca.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card">
      <SectionHead
        title="White-label Enterprise"
        description="Aplica tu marca, colores y dominio. Los cambios se reflejan al instante."
      />
      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}
      <form onSubmit={saveBranding}>
        <div className="form-grid">
          <label className="form-field">
            <span>Nombre de marca</span>
            <input
              value={form.brand_name}
              onChange={(event) => setForm((current) => ({ ...current, brand_name: event.target.value }))}
              placeholder="Mi Empresa"
            />
          </label>
          <label className="form-field">
            <span>Color primario</span>
            <input
              type="color"
              value={form.brand_primary_color}
              onChange={(event) => setForm((current) => ({ ...current, brand_primary_color: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span>Color de acento</span>
            <input
              type="color"
              value={form.brand_accent_color}
              onChange={(event) => setForm((current) => ({ ...current, brand_accent_color: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span>Logo (URL)</span>
            <input
              value={form.logo_url}
              onChange={(event) => setForm((current) => ({ ...current, logo_url: event.target.value }))}
              placeholder="https://cdn.empresa.cl/logo.svg"
            />
          </label>
          <label className="form-field">
            <span>Email de soporte</span>
            <input
              type="email"
              value={form.support_email}
              onChange={(event) => setForm((current) => ({ ...current, support_email: event.target.value }))}
              placeholder="soporte@empresa.cl"
            />
          </label>
          <label className="form-field">
            <span>Dominio personalizado</span>
            <input
              value={form.custom_domain}
              onChange={(event) => setForm((current) => ({ ...current, custom_domain: event.target.value }))}
              placeholder="compras.empresa.cl"
            />
          </label>
          <label className="form-field checkbox-field">
            <input
              type="checkbox"
              checked={form.hide_powered_by}
              onChange={(event) => setForm((current) => ({ ...current, hide_powered_by: event.target.checked }))}
            />
            <span>Ocultar “powered by NEXORA”</span>
          </label>
        </div>
        <div className="brand-preview">
          <div
            className="brand-preview-mark"
            style={{ background: `linear-gradient(145deg, ${form.brand_primary_color}, ${form.brand_accent_color})` }}
          >
            {form.logo_url ? <img src={form.logo_url} alt="" /> : (form.brand_name || "N").slice(0, 1)}
          </div>
          <div>
            <strong>{form.brand_name || "NEXORA"}</strong>
            <span>Compras auditadas</span>
          </div>
        </div>
        <div className="form-actions">
          <button type="submit" className="button primary" disabled={pending}>
            {pending ? "Guardando…" : "Guardar marca"}
          </button>
        </div>
      </form>
    </section>
  );
}

function OnboardingTab({ onNavigate, onTab }) {
  const [data, setData] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await api("/api/enterprise/onboarding");
      setData(result);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudo cargar el onboarding.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function seedDemo() {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const result = await api("/api/enterprise/onboarding/demo", { method: "POST", body: "{}" });
      setSuccess(result.already_seeded ? "Los datos demo ya estaban cargados." : "Datos demo cargados.");
      load();
    } catch (err) {
      setError(err.message || "No se pudieron cargar los datos demo.");
    } finally {
      setPending(false);
    }
  }

  async function dismiss() {
    setPending(true);
    try {
      await api("/api/enterprise/onboarding", {
        method: "PATCH",
        body: JSON.stringify({ dismissed: true }),
      });
      load();
    } catch (err) {
      setError(err.message || "No se pudo actualizar el onboarding.");
    } finally {
      setPending(false);
    }
  }

  function goStep(key) {
    const target = STEP_TARGETS[key];
    if (!target) return;
    if (target.page) onNavigate(target.page);
    if (target.tab) onTab(target.tab);
  }

  return (
    <div className="stack">
      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}
      <section className="card">
        <SectionHead
          title="Onboarding guiado"
          description="Completa los pasos clave para obtener valor desde el primer día."
        >
          <button type="button" className="button primary small" onClick={seedDemo} disabled={pending}>
            <SparkIcon /> Cargar datos demo
          </button>
          <button type="button" className="button ghost small" onClick={dismiss} disabled={pending || data?.dismissed}>
            Ocultar guía
          </button>
        </SectionHead>
        {!data ? (
          <div className="empty-state">Cargando progreso…</div>
        ) : (
          <>
            <div className="onboarding-progress">
              <div className="onboarding-track">
                <span style={{ width: `${data.percentage}%` }} />
              </div>
              <strong>{data.completed}/{data.total} pasos · {data.percentage}%</strong>
            </div>
            <div className="onboarding-steps">
              {data.labels.map((step) => (
                <div key={step.key} className={`onboarding-step ${step.done ? "done" : ""}`}>
                  <span className="onboarding-check">{step.done ? <CheckIcon /> : null}</span>
                  <div>
                    <strong>{step.label}</strong>
                    <small>{step.done ? "Completado" : "Pendiente"}</small>
                  </div>
                  {!step.done ? (
                    <button type="button" className="button ghost small" onClick={() => goStep(step.key)}>
                      Ir <ArrowRightIcon />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default function EnterprisePage({ onNavigate }) {
  const { canManage } = useAuth();
  const [tab, setTab] = useState("roi");

  if (!canManage) {
    return (
      <section className="card">
        <div className="empty-state">
          <ShieldIcon />
          <h2>Solo administradores</h2>
          <p>La suite Enterprise requiere rol owner o admin.</p>
        </div>
      </section>
    );
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><SparkIcon /> Suite Enterprise</div>
          <h2>Inteligencia y control</h2>
          <p>ROI, proveedores, alertas, integraciones, seguridad y white-label en un solo lugar.</p>
        </div>
      </section>

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Secciones Enterprise">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`settings-nav-item ${tab === item.id ? "active" : ""}`}
              onClick={() => setTab(item.id)}
            >
              <item.icon />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="settings-content">
          {tab === "roi" ? <RoiTab /> : null}
          {tab === "scorecards" ? <ScorecardsTab /> : null}
          {tab === "alerts" ? <AlertsTab /> : null}
          {tab === "integrations" ? <IntegrationsTab /> : null}
          {tab === "security" ? <SecurityTab /> : null}
          {tab === "branding" ? <BrandingTab /> : null}
          {tab === "onboarding" ? <OnboardingTab onNavigate={onNavigate} onTab={setTab} /> : null}
        </div>
      </div>
    </div>
  );
}
