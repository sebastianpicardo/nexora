import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import {
  ArrowRightIcon,
  BellIcon,
  CheckIcon,
  ClockIcon,
  DocumentsIcon,
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
    maturity: "operativo",
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
    maturity: "operativo",
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
    maturity: "a_medida",
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
    maturity: "proximamente",
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
    maturity: "a_medida",
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
    maturity: "proximamente",
    actions: [
      { id: "save_drive", label: "Guardar en Drive", primary: true, icon: DocumentsIcon },
      { id: "sso_login", label: "Iniciar sesión con Google", icon: LockIcon },
    ],
  },
];

const MATURITY_LABELS = {
  operativo: "Operativo",
  a_medida: "A medida",
  proximamente: "Próximamente",
};

const HISTORY_STORAGE_PREFIX = "nexora.search_history";
const HISTORY_LIMIT = 20;
const RUT_RE = /^\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]$/;

function historyConfig(entry) {
  const data = entry?.result_data || {};
  if (entry?.action === "search_items") {
    return {
      query: entry.query || data.query || "",
      mode: data.mode || entry.mode || "all",
    };
  }
  if (entry?.action === "validate_rut") {
    return { rut: entry.query || data.rut || "" };
  }
  return {
    name: entry.query || data.name || "",
    order_by: data.order_by || entry.order_by || "ranking",
  };
}

function historyDedupeKey(entry) {
  return [entry?.provider || "", entry?.action || "", (entry?.query || "").trim().toLowerCase()].join("|");
}

function sortHistory(entries) {
  return [...entries].sort(
    (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
  );
}

function mergeHistory(...groups) {
  const map = new Map();
  for (const group of groups) {
    for (const entry of group || []) {
      if (!entry?.provider || !entry?.action) continue;
      const key = historyDedupeKey(entry);
      const current = map.get(key);
      if (!current || new Date(entry.created_at || 0) >= new Date(current.created_at || 0)) {
        map.set(key, entry);
      }
    }
  }
  return sortHistory([...map.values()]).slice(0, HISTORY_LIMIT);
}

function readLocalHistory(userId) {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(`${HISTORY_STORAGE_PREFIX}.${userId || "anon"}`);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalHistory(userId, entries) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      `${HISTORY_STORAGE_PREFIX}.${userId || "anon"}`,
      JSON.stringify(entries.slice(0, HISTORY_LIMIT))
    );
  } catch {
    // El historial del servidor sigue disponible aunque localStorage esté bloqueado.
  }
}

function RutValidator({ running, disabled, onValidate }) {
  const [rut, setRut] = useState("");
  const [error, setError] = useState("");

  function submit(event) {
    event.preventDefault();
    const value = rut.trim();
    if (!value) {
      setError("Ingresa el RUT que quieres validar.");
      return;
    }
    if (!RUT_RE.test(value)) {
      setError("Formato esperado: 12.345.678-9.");
      return;
    }
    setError("");
    onValidate({ rut: value });
  }

  return (
    <form className="rut-validator" onSubmit={submit}>
      <label className="form-field">
        <span>RUT del proveedor</span>
        <div className="rut-validator-row">
          <input
            type="text"
            inputMode="text"
            value={rut}
            onChange={(event) => setRut(event.target.value)}
            placeholder="Ej: 76.123.456-7"
            aria-label="RUT del proveedor"
          />
          <button type="submit" className="button primary" disabled={running || disabled}>
            <CheckIcon />
            {running ? "Validando..." : "Validar RUT"}
          </button>
        </div>
        <p className="muted small">Valida el dígito verificador y el formato chileno.</p>
      </label>
      {error ? <div className="integration-error">{error}</div> : null}
    </form>
  );
}

function ProviderCard({ provider, status, onConfiguredAction, recentSearches }) {
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
  const visibleActions = provider.actions.filter(
    (action) => !(provider.id === "sii" && action.id === "validate_rut")
  );
  const validateRutAction = provider.actions.find((action) => action.id === "validate_rut");
  const maturity =
    status?.available === false ? "proximamente" : provider.maturity || "operativo";

  return (
    <div className="integration-card">
      <div className="integration-card-head" style={{ borderLeft: `4px solid ${provider.color}` }}>
        <div className="integration-icon" style={{ background: `${provider.color}20`, color: provider.color }}>
          <provider.icon />
        </div>
        <div>
          <div className="integration-name">
            {provider.name}
            <span className={`badge maturity-${maturity}`}>
              {MATURITY_LABELS[maturity] || MATURITY_LABELS.operativo}
            </span>
          </div>
          <p className="integration-desc">{provider.description}</p>
        </div>
      </div>
      {provider.id === "sii" && validateRutAction ? (
        <RutValidator
          running={running === validateRutAction.id}
          disabled={status?.available === false}
          onValidate={(config) => runAction(validateRutAction, config)}
        />
      ) : null}
      <div className="integration-actions">
        {visibleActions.map((action) => (
          <button
            key={action.id}
            type="button"
            className={`integration-button ${action.primary ? "integration-button-primary" : "integration-button-ghost"}`}
            disabled={running === action.id || status?.available === false || action.enabled === false}
            title={status?.available === false ? "Próximamente" : action.enabled === false ? "Acción no disponible todavía" : undefined}
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
                  const action = provider.actions.find((a) => a.id === h.action);
                  if (!action) return;
                  runAction(action, historyConfig(h));
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
      const config = historyConfig(latest);
      setQuery(config.query || "");
      setMode(config.mode || "all");
    }
    if (latest && isSuppliers && !supplierName) {
      const config = historyConfig(latest);
      setSupplierName(config.name || "");
      setOrderBy(config.order_by || "ranking");
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
                    const config = historyConfig(h);
                    if (isItems) {
                      setQuery(config.query || "");
                      setMode(config.mode || "all");
                    }
                    if (isSuppliers) {
                      setSupplierName(config.name || "");
                      setOrderBy(config.order_by || "ranking");
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
  const [saveError, setSaveError] = useState("");

  const handleSave = async () => {
    setSaving(true);
    setSaveError("");
    try {
      const ok = onSaveHistory ? await onSaveHistory(result) : true;
      if (ok === false) {
        setSaved(false);
        setSaveError("No se pudo guardar el historial. Inténtalo nuevamente.");
        return;
      }
      setSaved(true);
    } catch {
      setSaved(false);
      setSaveError("No se pudo guardar el historial. Inténtalo nuevamente.");
    } finally {
      setSaving(false);
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
        {saveError ? <div className="integration-error">{saveError}</div> : null}
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

export default function NativeIntegrationsPage() {
  const { user } = useAuth();
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openResult, setOpenResult] = useState(null);
  const [openHistory, setOpenHistory] = useState(null);
  const [searchHistory, setSearchHistory] = useState([]);
  const [backupAvailable, setBackupAvailable] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const requests = [
        api("/api/integrations/native/status"),
        api("/api/user/search-history?limit=20").catch(() => ({ items: [] })),
      ];
      if (user?.role === "super_admin") {
        requests.push(api("/api/backups/status").catch(() => ({ available: true })));
      }
      const [statusData, historyData, backupStatus] = await Promise.all(requests);
      const merged = mergeHistory(historyData?.items || [], readLocalHistory(user?.id));
      setProviders(statusData.providers || []);
      setSearchHistory(merged);
      writeLocalHistory(user?.id, merged);
      setBackupAvailable(backupStatus?.available !== false);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las integraciones.");
      setBackupAvailable(true);
    } finally {
      setLoading(false);
    }
  }, [user?.role, user?.id]);

  useEffect(() => {
    load();
  }, [load]);

  const saveSearch = useCallback(async (providerId, actionId, config, result) => {
    const query = config.query || config.name || config.rut || "";
    const now = new Date().toISOString();
    const payload = {
      ...result,
      ...config,
      provider: providerId,
      action: actionId,
      query,
    };
    const localEntry = {
      id: `local-${providerId}-${actionId}-${query}-${now}`,
      provider: providerId,
      action: actionId,
      query,
      result_summary: result.note || result.mensaje || "Ejecutado correctamente.",
      result_data: payload,
      created_at: now,
      local: true,
    };
    setSearchHistory((current) => {
      const merged = mergeHistory([localEntry], current);
      writeLocalHistory(user?.id, merged);
      return merged;
    });

    if (!user) return true;
    try {
      const response = await api("/api/user/search-history", {
        method: "POST",
        body: JSON.stringify({
          provider: providerId,
          action: actionId,
          query,
          result_summary: localEntry.result_summary,
          result_data: payload,
        }),
      });
      if (response.saved === false) return true;
      const serverEntry = response.id ? response : null;
      setSearchHistory((current) => {
        const merged = mergeHistory(serverEntry ? [serverEntry] : [], [localEntry], current);
        writeLocalHistory(user?.id, merged);
        return merged;
      });
      return true;
    } catch {
      return true;
    }
  }, [user]);

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Integraciones nativas</div>
          <h2>Conecta tus herramientas</h2>
          <p>
            Usa hoy las integraciones operativas y planifica las que requieren configuración a
            medida. Las marcadas como Próximamente no ejecutan acciones todavía.
          </p>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <div className="integration-legend">
        <span><i className="badge maturity-operativo">Operativo</i> Lista para usar hoy.</span>
        <span><i className="badge maturity-a_medida">A medida</i> Requiere configuración o exportación manual.</span>
        <span><i className="badge maturity-proximamente">Próximamente</i> Visible para planificación.</span>
      </div>

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
                  status={status}
                  onConfiguredAction={(prov, act, data, config) => {
                    const result = {
                      ...data,
                      ...config,
                      provider: prov.id,
                      action: act.id,
                      provider_name: prov.name,
                    };
                    setOpenResult(result);
                    saveSearch(prov.id, act.id, config, data);
                  }}
                  recentSearches={searchHistory}
                />
              );
            })}
          </div>
        </section>
      )}

      {user?.role === "super_admin" && <BackupSection available={backupAvailable} />}

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
          onSaveHistory={(result) =>
            saveSearch(result.provider, result.action, historyConfig(result), result)
          }
        />
      )}
      {openHistory && (
        <SearchHistoryModal
          history={openHistory}
          onClose={() => setOpenHistory(null)}
          onLoadHistory={(h) => {
            const config = historyConfig(h);
            const data = h.result_data || {};
            setOpenHistory(null);
            setOpenResult({
              ...data,
              ...config,
              provider: h.provider,
              action: h.action,
              provider_name: h.provider,
              query: h.query,
              results: data.results || [],
              invoices: data.invoices || [],
              note: h.result_summary,
              total: data.total,
              mode: config.mode,
              order_by: config.order_by,
            });
          }}
        />
      )}

    </div>
  );
}
