import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDateTime, labelize } from "../lib/format";
import { ArrowRightIcon, BellIcon, CheckIcon, DocumentsIcon, LockIcon, SearchIcon, SuppliersIcon } from "../components/Icons";

const PROVIDERS = [
  {
    id: "chilecompra",
    name: "ChileCompra",
    icon: SearchIcon,
    description: "Compara precios con el mercado público, busca proveedores registrados e importa órdenes de compra desde ChileCompra.",
    actions: [
      { id: "search_items", label: "Buscar productos", primary: true, icon: SearchIcon },
      { id: "search_suppliers", label: "Buscar proveedores", icon: SuppliersIcon },
      { id: "import_order", label: "Importar orden", icon: ArrowRightIcon },
    ],
  },
  {
    id: "sii",
    name: "SII",
    icon: CheckIcon,
    description: "Valida RUT de proveedores, obtiene facturas electrónicas y concilia documentos contra el Servicio de Impuestos Internos.",
    actions: [
      { id: "validate_rut", label: "Validar RUT", primary: true, icon: CheckIcon },
      { id: "fetch_invoices", label: "Obtener facturas", icon: DocumentsIcon },
      { id: "reconcile", label: "Conciliar documentos", icon: CheckIcon },
    ],
  },
  {
    id: "erp",
    name: "ERP",
    icon: ArrowRightIcon,
    description: "Sincroniza proveedores, envía aprobaciones como órdenes de compra e importa facturas desde tu sistema de gestión.",
    actions: [
      { id: "sync_suppliers", label: "Sincronizar proveedores", primary: true, icon: SuppliersIcon },
      { id: "send_approval", label: "Enviar aprobación", icon: ArrowRightIcon },
      { id: "import_invoices", label: "Importar facturas", icon: DocumentsIcon },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    icon: BellIcon,
    description: "Recibe alertas de alzas de precio y aprueba compras directamente desde tu canal de Slack.",
    actions: [
      { id: "notify", label: "Notificar en canal", primary: true, icon: BellIcon },
      { id: "approve_from_slack", label: "Aprobar desde Slack", icon: CheckIcon },
    ],
  },
  {
    id: "webhook",
    name: "Webhooks",
    icon: ArrowRightIcon,
    description: "Envía eventos automáticos a otros sistemas de tu empresa cuando se procesa un documento o se aprueba una compra.",
    actions: [
      { id: "send_event", label: "Enviar evento", primary: true, icon: ArrowRightIcon },
    ],
  },
  {
    id: "google_workspace",
    name: "Google Workspace",
    icon: LockIcon,
    description: "Inicia sesión con tu cuenta de empresa, guarda documentos en Drive y restringe el acceso por dominio.",
    actions: [
      { id: "save_drive", label: "Guardar en Drive", primary: true, icon: DocumentsIcon },
      { id: "sso_login", label: "Iniciar con Google", icon: LockIcon },
    ],
  },
];

function ProviderCard({ provider, connected, onAction }) {
  const [running, setRunning] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runAction = useCallback(async (action) => {
    setRunning(action.id);
    setResult(null);
    setError(null);
    try {
      const data = await api(`/api/integrations/native/${provider.id}/${action.id}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setResult(data);
    } catch (err) {
      setError(err.message || "No se pudo ejecutar la acción.");
    } finally {
      setRunning(null);
    }
  }, [provider.id]);

  return (
    <div className="integration-card">
      <div className="integration-card-head">
        <div className="integration-icon">
          <provider.icon />
        </div>
        <div>
          <div className="integration-name">
            {provider.name}
            <span className={`integration-status ${connected ? "connected" : "disconnected"}`}>
              {connected ? "Conectado" : "Desconectado"}
            </span>
          </div>
          <p className="integration-desc">{provider.description}</p>
        </div>
      </div>
      <div className="integration-actions">
        {provider.actions.map((action) => (
          <button
            key={action.id}
            type="button"
            className={`integration-button ${action.primary ? "integration-button-primary" : "integration-button-ghost"} ${!connected ? "integration-button-disabled" : ""}`}
            disabled={!connected || running === action.id}
            onClick={() => runAction(action)}
          >
            {running === action.id ? "Procesando…" : null}
            {!running && <action.icon />}
            {!running && action.label}
          </button>
        ))}
      </div>
      {result ? (
        <div className="integration-result">
          <strong>Resultado:</strong> {result.note || result.status || "Ejecutado correctamente."}
        </div>
      ) : null}
      {error ? <div className="integration-error">{error}</div> : null}
      {!connected && (
        <div className="integration-note">
          Esta integración requiere configuración técnica. Pídele a tu administrador que la active desde
          Enterprise → Integraciones.
        </div>
      )}
    </div>
  );
}

export default function NativeIntegrationsPage() {
  const { canManage } = useAuth();
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api("/api/integrations/native/status");
      setProviders(data.providers || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las integraciones.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Integraciones nativas</div>
          <h2>Conecta tus herramientas</h2>
          <p>
            Activa las integraciones que usa tu empresa. Desde un documento o proveedor puedes lanzar
            acciones directamente: buscar precios en ChileCompra, validar RUT en el SII, enviar aprobaciones al ERP,
            notificar en Slack o guardar en Google Drive.
          </p>
        </div>
        {canManage ? (
          <button type="button" className="button primary">
            <ArrowRightIcon /> Configurar integraciones (admin)
          </button>
        ) : null}
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {loading ? (
        <div className="empty-state">Cargando integraciones…</div>
      ) : (
        <section className="card">
          <div className="integration-grid">
            {PROVIDERS.map((provider) => {
              const status = providers.find((p) => p.provider === provider.id);
              const connected = status?.connected || false;
              return (
                <ProviderCard key={provider.id} provider={provider} connected={connected} />
              );
            })}
          </div>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>¿Desde dónde se usan?</h2>
            <p>Cada integración tiene acciones contextuales en los módulos de la plataforma.</p>
          </div>
        </div>
        <div className="integration-contexts">
          <div className="context-item">
            <DocumentsIcon />
            <div>
              <strong>Documentos</strong>
              <p>Buscar precios de referencia en ChileCompra, validar RUT en SII, guardar en Drive.</p>
            </div>
          </div>
          <div className="context-item">
            <SuppliersIcon />
            <div>
              <strong>Proveedores</strong>
              <p>Ver si están registrados en ChileCompra o validados en el SII.</p>
            </div>
          </div>
          <div className="context-item">
            <CheckIcon />
            <div>
              <strong>Aprobaciones</strong>
              <p>Enviar orden al ERP, notificar en Slack al decidir.</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
