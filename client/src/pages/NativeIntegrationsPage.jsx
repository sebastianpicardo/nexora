import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import {
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  ClockIcon,
  DocumentsIcon,
  HelpIcon,
  HistoryIcon,
  LockIcon,
  SearchIcon,
  SuppliersIcon,
  XIcon,
  TrashIcon,
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
      { id: "sso_login", label: "Iniciar sesión con Google", icon: LockIcon },
    ],
  },
];

const HELP_RESPONSES = {
  hola: "¡Hola! Soy el asistente de NEXORA. Puedo ayudarte con: buscar precios en ChileCompra, validar RUT en SII, crear aprobaciones de compra, exportar a tu ERP, hacer backups y configurar tu marca blanca.",
  "hola!": "¡Hola! Soy el asistente de NEXORA. ¿En qué puedo ayudarte hoy?",
  "buenos dias": "¡Buenos días! ¿En qué puedo ayudarte? Puedo guiarte en el uso de NEXORA.",
  "buenas tardes": "¡Buenas tardes! ¿En qué puedo ayudarte?",
  precios: "Para buscar precios en ChileCompra, ve a la sección Integraciones y usa 'Buscar precios'. Puedes filtrar por producto o ver los mejores precios (más baratos).",
  rut: "Para validar un RUT chileno, ve a la sección Integraciones → SII y usa 'Validar RUT'. Ingresa el RUT y te diré si el formato es válido.",
  sii: "El SII te permite validar RUT de proveedores y obtener facturas electrónicas. Ve a Integraciones → SII para usarlo.",
  chilecompra: "ChileCompra te permite buscar precios de referencia del mercado público y proveedores registrados. Ve a Integraciones → ChileCompra.",
  aprobacion: "Para aprobar una compra, ve a la sección Aprobaciones. Allí puedes ver solicitudes pendientes y aprobarlas o rechazarlas.",
  aprobaciones: "Para aprobar una compra, ve a la sección Aprobaciones. Allí puedes ver solicitudes pendientes y aprobarlas o rechazarlas.",
  erp: "Para exportar a tu ERP, ve a Integraciones → ERP. Puedes exportar proveedores, enviar aprobaciones e importar facturas en archivos CSV listos para importar.",
  backup: "Para hacer un backup, ve a Integraciones → Backups. Nota: requiere que el servidor tenga pg_dump instalado. Si no está disponible, puedes exportar documentos individualmente desde Documentos.",
  drive: "Para guardar en Google Drive, ve a Integraciones → Google Workspace y usa 'Guardar en Drive'.",
  white: "Para configurar tu marca blanca (logo, colores, nombre), ve a Integraciones → Seguridad y marca (o Enterprise → White-label).",
  sso: "Para configurar SSO con Google Workspace, ve a Integraciones → Seguridad y marca. Allí puedes habilitar el inicio de sesión con Google y restringir el acceso por dominio.",
  ayuda: "Pregúntame sobre: precios, RUT, SII, ChileCompra, aprobaciones, ERP, backups, Drive, SSO o white-label. Prueba escribiendo una de esas palabras.",
  tutorial: "NEXORA tiene módulos de Documentos, Proveedores, Aprobaciones, Integraciones (ChileCompra, SII, ERP, Google Drive, Backups) y Configuración. Cada uno tiene acciones directas.",
  quienessomos: "NEXORA es una plataforma de auditoría de compras y precios para ferreterías y distribuidores industriales, ayudando a comparar precios, validar RUTs y gestionar documentos.",
};

function getHelpResponse(text) {
  const lower = text.toLowerCase().trim();
  for (const [key, response] of Object.entries(HELP_RESPONSES)) {
    if (lower.includes(key)) {
      return response;
    }
  }
  return "No entiendo tu consulta. Puedo ayudarte con: precios, RUT, SII, ChileCompra, aprobaciones, ERP, backups, Drive, SSO o white-label. Prueba escribiendo una de esas palabras.";
}

function ProviderCard({ provider, onConfiguredAction, recentSearches }) {
  const [running, setRunning] = useState(null);
  const [error, setError] = useState(null);
  const [configureModal, setConfigureModal] = useState(null);

  const runAction = useCallback(async (action, config) => {
    setRunning(action.id);
    setError(null);
    try {
      const body = { ...config };
      const data = await api(`/api/integrations/native/${provider.id}/${action.id}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      onConfiguredAction(provider, action, data, config);
    } catch (err) {
      setError(err.message || "No se pudo ejecutar la acción.");
    } finally {
      setRunning(null);
    }
  }, [provider.id, onConfiguredAction]);

  const openConfigure = (action) => {
    setConfigureModal(action);
    setError(null);
  };

  const closeConfigure = () => {
    setConfigureModal(null);
    setError(null);
  };

  const providerHistory = recentSearches.filter(
    (h) => h.provider === provider.id && (h.action === "search_items" || h.action === "search_suppliers")
  );

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
            onClick={() => {
              if (action.id === "search_items" || action.id === "search_suppliers") {
                openConfigure(action);
              } else {
                runAction(action, {});
              }
            }}
          >
            {running === action.id ? "Procesando…" : null}
            {!running && <action.icon />}
            {!running && action.label}
          </button>
        ))}
        {providerHistory.length > 0 && (
          <div className="recent-searches">
            <strong>Tus búsquedas recientes:</strong>
            {providerHistory.map((h) => (
              <button
                key={h.id}
                type="button"
                className="recent-search-chip"
                onClick={() => {
                  const config = h.action === "search_items" ? { query: h.query, mode: h.mode || "all" } : { name: h.query, order_by: h.order_by || "ranking" };
                  runAction({ ...provider.actions.find((a) => a.id === h.action), id: h.action }, config);
                }}
              >
                {h.query}
              </button>
            ))}
          </div>
        )}
      </div>
      {error ? <div className="integration-error">{error}</div> : null}

      {configureModal && (
        <IntegrationConfigModal
          provider={provider}
          action={configureModal}
          recentSearches={providerHistory}
          onClose={closeConfigure}
          onRun={(config) => {
            closeConfigure();
            runAction(configureModal, config);
          }}
        />
      )}
    </div>
  );
}

function IntegrationConfigModal({ provider, action, recentSearches, onClose, onRun }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("all");
  const [orderBy, setOrderBy] = useState("ranking");
  const [supplierName, setSupplierName] = useState("");

  const isItems = action.id === "search_items";
  const isSuppliers = action.id === "search_suppliers";

  // Precargar de la búsqueda más reciente si existe
  useEffect(() => {
    const latest = recentSearches[0];
    if (latest && isItems && !query) {
      setQuery(latest.query || "");
      setMode(latest.mode || "all");
    }
    if (latest && isSuppliers && !supplierName) {
      setSupplierName(latest.query || "");
      setOrderBy(latest.order_by || "ranking");
    }
  }, [recentSearches, isItems, isSuppliers, query, supplierName]);

  return (
    <div className="integration-modal-overlay" onClick={onClose}>
      <div className="integration-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{provider.name} — {action.label}</h3>
          <button type="button" className="icon-button" onClick={onClose}>
            <XIcon />
          </button>
        </div>
        <div className="modal-body">
          {recentSearches.length > 0 && (
            <div className="recent-searches">
              <strong>Búsquedas guardadas:</strong>
              {recentSearches.map((h) => (
                <button
                  key={h.id}
                  type="button"
                  className="recent-search-chip"
                  onClick={() => {
                    if (isItems) {
                      setQuery(h.query || "");
                      setMode(h.mode || "all");
                    }
                    if (isSuppliers) {
                      setSupplierName(h.query || "");
                      setOrderBy(h.order_by || "ranking");
                    }
                  }}
                >
                  {h.query}
                </button>
              ))}
            </div>
          )}
          {isItems && (
            <>
              <label className="form-field">
                <span>Buscar producto</span>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ej: tornillo, pintura, tubería"
                />
                <p className="muted small">Déjalo vacío para ver todos los productos.</p>
              </label>
              <div className="form-field">
                <span>Modo de búsqueda</span>
                <div className="radio-group">
                  <label className="radio-label">
                    <input type="radio" name="mode" value="all" checked={mode === "all"} onChange={() => setMode("all")} />
                    Todos los productos
                  </label>
                  <label className="radio-label">
                    <input type="radio" name="mode" value="cheapest" checked={mode === "cheapest"} onChange={() => setMode("cheapest")} />
                    Mejores precios (más baratos)
                  </label>
                </div>
              </div>
            </>
          )}
          {isSuppliers && (
            <>
              <label className="form-field">
                <span>Buscar proveedor por nombre</span>
                <input
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  placeholder="Ej: ferretería, pintura, tornillería"
                />
                <p className="muted small">Déjalo vacío para ver todos los proveedores.</p>
              </label>
              <label className="form-field">
                <span>Ordenar por</span>
                <select
                  value={orderBy}
                  onChange={(e) => setOrderBy(e.target.value)}
                >
                  <option value="ranking">Ranking general</option>
                  <option value="confidence">Mayor confianza</option>
                  <option value="price">Menor precio promedio</option>
                  <option value="complaints">Menos quejas</option>
                </select>
              </label>
            </>
          )}
        </div>
        <div className="modal-actions">
          <button type="button" className="button ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" className="button primary" onClick={() => onRun({ query, mode, name: supplierName, order_by: orderBy })}>
            <SearchIcon /> Buscar
          </button>
        </div>
      </div>
    </div>
  );
}

function IntegrationResultModal({ result, onClose, onViewHistory, onSaveHistory }) {
  const resultados = result.results || [];
  const invoices = result.invoices || [];

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const config = {
        query: result.query || "",
        mode: result.mode || "",
        name: result.query || "",
        order_by: result.order_by || "",
      };
      const response = await api("/api/user/search-history", {
        method: "POST",
        body: JSON.stringify({
          provider: result.provider,
          action: result.action,
          query: result.query || "",
          result_summary: result.note || result.mensaje || "Ejecutado correctamente.",
          result_data: result,
        }),
      });
      if (response.saved === false) {
        setSaved(false);
        return;
      }
      setSaved(true);
      setSaving(false);
      if (onSaveHistory) onSaveHistory();
    } catch {
      setSaving(false);
      setSaved(false);
    }
  };

  return (
    <div className="integration-modal-overlay" onClick={onClose}>
      <div className="integration-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{result.provider_name}</h3>
          <button type="button" className="icon-button" onClick={onClose}>
            <XIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="result-summary">
            <strong>Acción:</strong> {result.action}
            {result.query ? " · Filtro: \"" + result.query + "\"" : ""}
            {result.mode ? " · Modo: " + (result.mode === "cheapest" ? "Mejores precios" : "Todos") : ""}
            {result.order_by ? " · Orden: " + result.order_by : ""}
            {result.total !== undefined && <strong> · Total: {result.total}</strong>}
          </div>

          {resultados.length > 0 ? (
            <div className="result-table-wrap">
              {resultados[0].rut ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Proveedor</th>
                      <th>RUT</th>
                      <th>Región</th>
                      <th>Confianza</th>
                      <th>Ranking</th>
                      <th>Precio promedio</th>
                      <th>Quejas</th>
                      <th>Contacto</th>
                      <th>Teléfono</th>
                      <th>Email</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.map((r, i) => (
                      <tr key={i}>
                        <td>{r.name || "—"}</td>
                        <td className="mono">{r.rut || "—"}</td>
                        <td>{r.region || "—"}</td>
                        <td>{r.confianza ?? "—"}</td>
                        <td>{r.ranking ?? "—"}</td>
                        <td className="mono">${Number(r.precio_promedio ?? 0).toLocaleString("es-CL")}</td>
                        <td>{r.quejas ?? "—"}</td>
                        <td>{r.contacto || "—"}</td>
                        <td className="mono">{r.telefono || "—"}</td>
                        <td>{r.email || "—"}</td>
                        <td>{r.estado || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ítem</th>
                      <th>Categoría</th>
                      <th>Unidad</th>
                      <th>Precio ref.</th>
                      <th>Proveedor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.map((r, i) => (
                      <tr key={i}>
                        <td>{r.item || "—"}</td>
                        <td>{r.categoria || "—"}</td>
                        <td>{r.unit || "—"}</td>
                        <td className="mono">${Number(r.precio ?? 0).toLocaleString("es-CL")}</td>
                        <td>{r.proveedor || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="muted small">
                Precios de referencia estimados. No son cotizaciones oficiales de ChileCompra.
              </p>
            </div>
          ) : invoices.length > 0 ? (
            <div className="result-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Fecha</th>
                    <th>Monto</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((r, i) => (
                    <tr key={i}>
                      <td>{r.folio || r.id || "—"}</td>
                      <td>{r.fecha || "—"}</td>
                      <td className="mono">{r.monto || "—"}</td>
                      <td>{r.estado || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {(result.file || result.archivo) && (
            <div className="result-file">
              <strong>Archivo listo:</strong> {result.file || result.archivo}
              <p className="muted small">{result.note || ""}</p>
            </div>
          )}

          {!result.file && !resultados.length && !invoices.length && (
            <div className="result-note">
              <p>{result.note || result.mensaje || "Ejecutado correctamente."}</p>
              {result.payload && (
                <div className="result-payload">
                  <strong>Payload:</strong>
                  <pre>{JSON.stringify(result.payload, null, 2)}</pre>
                </div>
              )}
              {!result.payload && (
                <div className="result-details">
                  {Object.entries(result).map(([key, value]) => {
                    const skip = ["provider", "action", "note", "mensaje", "payload", "results", "invoices", "file", "archivo", "query", "mode", "order_by", "name", "total"];
                    if (skip.includes(key) || value === undefined || value === null) return null;
                    const label = key
                      .replace(/([A-Z])/g, " $1")
                      .replace(/^./, (str) => str.toUpperCase());
                    return (
                      <div key={key} className="result-detail-row">
                        <strong>{label}:</strong> {String(value)}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button type="button" className="button ghost" onClick={onClose}>
            Cerrar
          </button>
          {!saved && (
            <button
              type="button"
              className="button primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Guardando…" : (
                <>
                  <HistoryIcon /> Guardar en mi historial
                </>
              )}
            </button>
          )}
          {saved && (
            <button type="button" className="button ghost" disabled>
              <>
                <CheckIcon /> Guardado en tu historial
              </>
            </button>
          )}
          {onViewHistory ? (
            <button
              type="button"
              className="button ghost"
              onClick={onViewHistory}
            >
              <>
                <HistoryIcon /> Ver historial
              </>
            </button>
          ) : null}
          <button
            type="button"
            className="button primary"
            onClick={() => {
              window.print();
            }}
          >
            <>
              <DocumentsIcon /> Guardar PDF
            </>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Backup ── */

function BackupSection({ available }) {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api("/api/backups");
      setBackups(data.backups || []);
    } catch (err) {
      setBackups([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    setCreating(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/backups", { method: "POST" });
      setSuccess(data.message || "Backup creado correctamente.");
      setCreating(false);
      load();
    } catch (err) {
      setError(err.message || "No se pudo crear el backup.");
      setCreating(false);
    }
  };

  const handleDownload = (filename) => {
    downloadFile(`/api/backups/download/${filename}`, filename);
  };

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Backup y recuperación de base de datos</h2>
          <p>Protege toda la información de tu organización. Genera copias de seguridad y descárgalas.</p>
        </div>
      </div>

      {!available && (
        <div className="alert warning">
          <strong>Backup no disponible.</strong> El servidor no tiene <code>pg_dump</code> instalado.
          Contacta al administrador para habilitar copias de seguridad automáticas.
        </div>
      )}

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="backup-controls">
        <button
          type="button"
          className="button primary"
          disabled={creating || !available}
          onClick={handleCreate}
        >
          {creating ? "Creando backup…" : <><DocumentsIcon /> Crear backup ahora</>}
        </button>
      </div>

      {!available && (
        <div className="muted small">
          Los backups requieren configuración del servidor (pg_dump). Mientras tanto, exporta tus
          datos desde los módulos de Documentos, Proveedores y Aprobaciones.
        </div>
      )}

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Archivo</th>
              <th>Tamaño</th>
              <th>Creado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {backups.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty-cell">No hay backups creados aún.</td>
              </tr>
            ) : (
              backups.map((b) => (
                <tr key={b.filename}>
                  <td className="mono">{b.filename}</td>
                  <td className="mono">{Number(b.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                  <td>{b.created_at}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="button ghost icon-only"
                        onClick={() => handleDownload(b.filename)}
                        title="Descargar backup"
                      >
                        <DocumentsIcon />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SearchHistoryModal({ history, onClose, onLoadHistory }) {
  return (
    <div className="integration-modal-overlay" onClick={onClose}>
      <div className="integration-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Tu historial de búsquedas</h3>
          <button type="button" className="icon-button" onClick={onClose}>
            <XIcon />
          </button>
        </div>
        <div className="modal-body">
          {history.length === 0 ? (
            <div className="empty-state">
              <HistoryIcon />
              <p>No tienes búsquedas guardadas aún.</p>
              <small>Busca precios en ChileCompra o valida RUT en SII y luego guarda en tu historial desde el resultado.</small>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Proveedor</th>
                  <th>Acción</th>
                  <th>Filtro / Query</th>
                  <th>Fecha</th>
                  <th>Resultado</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td>{h.provider}</td>
                    <td>{h.action}</td>
                    <td className="mono truncate">{h.query || "—"}</td>
                    <td>{h.created_at}</td>
                    <td>
                      <button
                        type="button"
                        className="button ghost small"
                        onClick={() => {
                          onClose();
                          if (onLoadHistory) onLoadHistory(h);
                        }}
                      >
                        Cargar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="modal-actions">
          <button type="button" className="button ghost" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Chatbox de ayuda ── */

function HelpChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "¡Hola! Soy el asistente de NEXORA. ¿En qué puedo ayudarte hoy?",
      sender: "bot",
    },
  ]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { id: Date.now(), text: input, sender: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    try {
      const resp = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${import.meta.env.VITE_OPENAI_API_KEY || ""}`,
        },
        body: JSON.stringify({
          model: "gpt-4o-mini",
          messages: [
            { role: "system", content: "Eres un asistente experto de NEXORA, una plataforma de auditoría de compras y precios para ferreterías y distribuidores industriales. Responde en español, de forma breve y práctica. Ayuda con: buscar precios, validar RUT en SII, ChileCompra, aprobaciones de compras, integraciones ERP, backups y white-label." },
            { role: "user", content: input },
          ],
        }),
      });
      const data = await resp.json();
      const botText = data.choices?.[0]?.message?.content || "No pude procesar tu consulta. Intenta de nuevo.";
      setMessages((prev) => [...prev, { id: Date.now() + 1, text: botText, sender: "bot" }]);
    } catch {
      setMessages((prev) => [...prev, { id: Date.now() + 1, text: "El asistente no está disponible ahora. Intenta más tarde.", sender: "bot" }]);
    }
  };

  return (
    <div className="help-chat-container">
      {!open && (
        <button
          type="button"
          className="help-chat-fab"
          onClick={() => setOpen(true)}
          title="Asistente de ayuda"
          aria-label="Abrir asistente de ayuda"
        >
          <HelpIcon />
          <span className="help-badge">1</span>
        </button>
      )}
      {open && (
        <div className="help-chat-panel">
          <div className="help-chat-header">
            <div className="help-chat-title">
              <HelpIcon /> Asistencia NEXORA
            </div>
            <button type="button" className="help-chat-close" onClick={() => setOpen(false)}>
              <XIcon />
            </button>
          </div>
          <div className="help-chat-messages">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`help-chat-message ${m.sender}`}
              >
                <div className="help-chat-bubble">{m.text}</div>
              </div>
            ))}
          </div>
          <div className="help-chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Escribe tu consulta…"
            />
            <button type="button" className="help-chat-send" onClick={sendMessage} disabled={!input.trim()}>
              <ArrowRightIcon />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function NativeIntegrationsPage() {
  const { user } = useAuth();
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openResult, setOpenResult] = useState(null);
  const [openHistory, setOpenHistory] = useState(null);
  const [searchHistory, setSearchHistory] = useState([]);
  const [backupAvailable, setBackupAvailable] = useState(true);
  const [pendingHistoryId, setPendingHistoryId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statusData, historyData, backupStatus] = await Promise.all([
        api("/api/integrations/native/status"),
        api("/api/user/search-history?limit=20"),
        api("/api/backups/status"),
      ]);
      setProviders(statusData.providers || []);
      setSearchHistory(historyData.items || []);
      setBackupAvailable(backupStatus.available !== false);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las integraciones.");
      setBackupAvailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saveSearch = useCallback(async (providerId, actionId, config, result) => {
    if (!user) return;
    try {
      const response = await api("/api/user/search-history", {
        method: "POST",
        body: JSON.stringify({
          provider: providerId,
          action: actionId,
          query: config.query || config.name || "",
          result_summary: result.note || result.mensaje || "Ejecutado correctamente.",
          result_data: result,
        }),
      });
      if (response.saved === false) {
        // Migración no aplicada; silenciar
        return;
      }
      const historyData = await api("/api/user/search-history?limit=20");
      setSearchHistory(historyData.items || []);
    } catch {
      // No fallar la UI si no se puede guardar
    }
  }, [user]);

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
                <ProviderCard
                  key={provider.id}
                  provider={provider}
                  onConfiguredAction={(prov, act, data, config) => {
                    setOpenResult({ ...data, provider_name: prov.name });
                    saveSearch(prov.id, act.id, config, data);
                  }}
                  recentSearches={searchHistory}
                />
              );
            })}
          </div>
        </section>
      )}

      {user && user.role !== "viewer" && <BackupSection available={backupAvailable} />}

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

      {openResult && (
        <IntegrationResultModal
          result={openResult}
          onClose={() => setOpenResult(null)}
          onViewHistory={() =>
            setOpenHistory(
              searchHistory.filter(
                (h) => h.provider === openResult.provider && h.action === openResult.action
              )
            )
          }
          onSaveHistory={() => {
            setOpenResult(null);
            load();
          }}
        />
      )}
      {openHistory && (
        <SearchHistoryModal
          history={openHistory}
          onClose={() => setOpenHistory(null)}
          onLoadHistory={(h) => {
            setOpenHistory(null);
            setOpenResult({
              provider_name: h.provider,
              action: h.action,
              query: h.query,
              results: (h.result_data && h.result_data.results) || [],
              note: h.result_summary,
              total: h.result_data && h.result_data.total,
              mode: h.mode,
              order_by: h.order_by,
            });
          }}
        />
      )}

      <HelpChat />
    </div>
  );
}
