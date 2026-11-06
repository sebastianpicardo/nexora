import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import {
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  DocumentsIcon,
  LockIcon,
  SearchIcon,
  SuppliersIcon,
} from "../components/Icons";

const PROVIDERS = [
  {
    id: "chilecompra",
    name: "ChileCompra",
    icon: SearchIcon,
    description: "Compara precios de referencia del mercado público y busca proveedores para tus compras de ferretería.",
    color: "#10b981",
    actions: [
      { id: "search_items", label: "Buscar precios", primary: true, icon: SearchIcon },
      { id: "search_suppliers", label: "Buscar proveedores", icon: SuppliersIcon },
      { id: "import_order", label: "Importar orden", icon: ArrowRightIcon },
    ],
  },
  {
    id: "sii",
    name: "SII",
    icon: CheckIcon,
    description: "Valida el formato RUT de tus proveedores y prepara documentos para conciliación tributaria.",
    color: "#059669",
    actions: [
      { id: "validate_rut", label: "Validar RUT", primary: true, icon: CheckIcon },
      { id: "fetch_invoices", label: "Facturas electrónicas", icon: DocumentsIcon },
      { id: "reconcile", label: "Conciliar documentos", icon: CheckIcon },
    ],
  },
  {
    id: "erp",
    name: "ERP / Contabilidad",
    icon: ArrowRightIcon,
    description: "Exporta proveedores, órdenes de compra y facturas en archivos listos para importar a cualquier sistema.",
    color: "#0f766e",
    actions: [
      { id: "sync_suppliers", label: "Exportar proveedores", primary: true, icon: SuppliersIcon },
      { id: "send_approval", label: "Enviar aprobación", icon: ArrowRightIcon },
      { id: "import_invoices", label: "Importar facturas", icon: DocumentsIcon },
    ],
  },
  {
    id: "slack",
    name: "Slack / Notificaciones",
    icon: BellIcon,
    description: "Prepara avisos de compras pendientes y aprobaciones para compartir con tu equipo.",
    color: "#3b82f6",
    actions: [
      { id: "notify", label: "Notificar al equipo", primary: true, icon: BellIcon },
      { id: "approve_from_slack", label: "Aprobar compra", icon: CheckIcon },
    ],
  },
  {
    id: "webhook",
    name: "Webhooks",
    icon: ArrowRightIcon,
    description: "Genera payloads para conectar NEXORA con otros sistemas de tu empresa.",
    color: "#6366f1",
    actions: [
      { id: "send_event", label: "Enviar evento", primary: true, icon: ArrowRightIcon },
    ],
  },
  {
    id: "google_workspace",
    name: "Google Workspace",
    icon: LockIcon,
    description: "Guarda documentos y accede con tu cuenta de Google de la empresa.",
    color: "#7c3aed",
    actions: [
      { id: "save_drive", label: "Guardar en Drive", primary: true, icon: DocumentsIcon },
      { id: "sso_login", label: "Iniciar con Google", icon: LockIcon },
    ],
  },
];

function ProviderCard({ provider, onAction }) {
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
      <div className="integration-card-head" style={{ borderLeft: `4px solid ${provider.color}` }}>
        <div className="integration-icon" style={{ background: `${provider.color}20`, color: provider.color }}>
          <provider.icon />
        </div>
        <div>
          <div className="integration-name">{provider.name}</div>
          <p className="integration-desc">{provider.description}</p>
        </div>
      </div>
      <div className="integration-actions">
        {provider.actions.map((action) => (
          <button
            key={action.id}
            type="button"
            className={`integration-button ${action.primary ? "integration-button-primary" : "integration-button-ghost"}`}
            disabled={running === action.id}
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
          <strong>Resultado:</strong> {result.note || result.mensaje || "Ejecutado correctamente."}
          {result.resultados ? (
            <ul className="reference-list">
              {result.resultados.slice(0, 5).map((r, i) => (
                <li key={i}>
                  {r.item || r.name} — {r.precio !== undefined ? `$${r.precio}` : r.status || ""}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {error ? <div className="integration-error">{error}</div> : null}
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
            Todas las integraciones están listas para usar. Desde cualquier documento, proveedor o aprobación puedes
            lanzar acciones: buscar precios de referencia en ChileCompra, validar RUT en el SII, exportar a tu ERP,
            notificar a tu equipo o guardar en Google Drive. No necesitas configurar claves ni APIs.
          </p>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      {loading ? (
        <div className="empty-state">Cargando integraciones…</div>
      ) : (
        <section className="card">
          <div className="integration-grid">
            {PROVIDERS.map((provider) => {
              const status = providers.find((p) => p.provider === provider.id);
              return (
                <ProviderCard key={provider.id} provider={provider} onAction={status?.actions} />
              );
            })}
          </div>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Desde dónde se usan</h2>
            <p>Cada integración tiene acciones directas en los módulos de la plataforma.</p>
          </div>
        </div>
        <div className="integration-contexts">
          <div className="context-item">
            <DocumentsIcon />
            <div>
              <strong>Documentos</strong>
              <p>Buscar precios en ChileCompra, validar RUT en SII, guardar en Google Drive.</p>
            </div>
          </div>
          <div className="context-item">
            <SuppliersIcon />
            <div>
              <strong>Proveedores</strong>
              <p>Validar RUT chileno y buscar referencias en ChileCompra.</p>
            </div>
          </div>
          <div className="context-item">
            <CheckIcon />
            <div>
              <strong>Aprobaciones</strong>
              <p>Exportar orden al ERP y notificar al equipo por email o Slack.</p>
            </div>
          </div>
        </div>
      </section>

      <div className="integration-note">
        <strong>Nota:</strong> Algunos resultados son referencias estimadas. Para consultas en vivo con datos reales de
        ChileCompra o SII se requieren credenciales de esos portales, pero el sistema funciona sin ellas desde el primer día.
      </div>
    </div>
  );
}
