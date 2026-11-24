import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, downloadFile } from "../lib/api";
import { formatMoney } from "../lib/format";
import {
  ArrowRightIcon,
  CheckIcon,
  DocumentsIcon,
  HistoryIcon,
  SearchIcon,
  SuppliersIcon,
  XIcon,
} from "../components/Icons";

const PROVIDERS = [
  {
    id: "chilecompra",
    name: "Compra Ágil · ChileCompra",
    icon: SearchIcon,
    description:
      "Revisa oportunidades públicas reales de hasta 100 UTM, cargadas desde la API o importadas por CSV. Nunca mostramos datos inventados.",
    color: "#10b981",
    maturity: "operativo",
    actions: [
      { id: "search_items", label: "Ver oportunidades", primary: true, icon: SearchIcon },
    ],
  },
  {
    id: "sii",
    name: "SII · Validación de RUT",
    icon: CheckIcon,
    description:
      "Valida el dígito verificador de cualquier RUT chileno y consulta el historial real de ese proveedor en tu organización.",
    color: "#059669",
    maturity: "operativo",
    actions: [
      { id: "validate_rut", label: "Validar RUT", primary: true, icon: CheckIcon },
    ],
  },
  {
    id: "erp",
    name: "ERP / Contabilidad",
    icon: ArrowRightIcon,
    description:
      "Exporta proveedores, órdenes de compra y facturas a CSV real, listo para importar a tu sistema.",
    color: "#0f766e",
    maturity: "operativo",
    actions: [
      { id: "sync_suppliers", label: "Exportar proveedores", primary: true, icon: SuppliersIcon },
      { id: "send_approval", label: "Exportar órdenes", icon: ArrowRightIcon },
      { id: "import_invoices", label: "Exportar facturas", icon: DocumentsIcon },
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
    const clean = value.replace(/[^0-9kK]/g, "").toUpperCase();
    if (clean.length < 2 || clean.length > 9) {
      setError("Ingresa un RUT válido. Acepta puntos, guion y K mayúscula o minúscula.");
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
            placeholder="Ej: 76.123.456-7 o 76123456K"
            aria-label="RUT del proveedor"
          />
          <button type="submit" className="button primary" disabled={running || disabled}>
            <CheckIcon />
            {running ? "Validando..." : "Validar RUT"}
          </button>
        </div>
        <p className="muted small">
          Acepta cualquier formato: 12.345.678-9, 12345678-9, 123456789 o 12345678K.
        </p>
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
  const runnableActions = provider.actions.filter(
    (action) => action.enabled !== false && !(provider.id === "sii" && action.id === "validate_rut")
  );
  const validateRutAction = provider.actions.find((action) => action.id === "validate_rut");
  const maturity =
    status?.available === false ? "proximamente" : provider.maturity || "operativo";
  const operational = maturity === "operativo" && status?.available !== false;

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
      {operational && provider.id === "sii" && validateRutAction ? (
        <RutValidator
          running={running === validateRutAction.id}
          onValidate={(config) => runAction(validateRutAction, config)}
        />
      ) : null}
      {operational ? (
        <div className="integration-actions">
          {runnableActions.map((action) => (
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
      ) : (
        <div className="integration-unavailable">
          <strong>Próximamente</strong>
          <p>
            {provider.id === "erp"
              ? "La exportación de datos ya está disponible desde los módulos de Documentos, Excepciones y Proveedores."
              : "Esta integración todavía no ejecuta acciones. La mostramos para que puedas planificar su adopción."}
          </p>
        </div>
      )}
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

function SiiResult({ result }) {
  const supplier = result.supplier;
  const stats = result.stats || {};
  const currency = result.currency || "CLP";
  const recent = result.recent_documents || [];
  const rcv = result.rcv_documents || [];
  const valid = Boolean(result.valido);

  return (
    <div className="stack">
      <div className="result-summary">
        <span className={`badge ${valid ? "status-approved" : "status-rejected"}`}>
          {result.estado || (valid ? "RUT válido" : "RUT inválido")}
        </span>{" "}
        <strong className="mono">{result.rut_formatted || result.rut || "—"}</strong>
      </div>

      {supplier ? (
        <div className="enterprise-metrics">
          <div className="enterprise-metric">
            <span>Proveedor</span>
            <strong>{supplier.name || "—"}</strong>
            <small>{supplier.email || "Sin email registrado"}</small>
          </div>
          <div className="enterprise-metric">
            <span>RUT registrado</span>
            <strong className="mono">{supplier.tax_id || "—"}</strong>
            <small>{supplier.created_at ? `Registrado el ${String(supplier.created_at).slice(0, 10)}` : ""}</small>
          </div>
        </div>
      ) : (
        <div className="result-note">
          <p>
            Este RUT no está registrado como proveedor en tu organización. Puedes agregarlo desde el
            módulo Directorio o subir un documento que lo incluya.
          </p>
        </div>
      )}

      <div className="enterprise-metrics">
        <div className="enterprise-metric">
          <span>Documentos</span>
          <strong>{stats.documents ?? 0}</strong>
        </div>
        <div className="enterprise-metric">
          <span>Ítems</span>
          <strong>{stats.items ?? 0}</strong>
        </div>
        <div className="enterprise-metric">
          <span>Gasto acumulado</span>
          <strong>{formatMoney(stats.spend || 0, currency)}</strong>
        </div>
        <div className="enterprise-metric">
          <span>Última compra</span>
          <strong>{stats.last_purchase || "—"}</strong>
        </div>
      </div>

      {recent.length > 0 ? (
        <div className="result-table-wrap">
          <h4>Documentos recientes</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Folio / Archivo</th>
                <th>Tipo</th>
                <th>Fecha</th>
                <th className="right">Total</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((d, i) => (
                <tr key={i}>
                  <td className="mono">{d.folio || d.original_filename || "—"}</td>
                  <td>{d.doc_type || "—"}</td>
                  <td>{d.document_date || "—"}</td>
                  <td className="right mono">{d.total ? d.total : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {rcv.length > 0 ? (
        <div className="result-table-wrap">
          <h4>RCV de compras</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Tipo</th>
                <th>Período</th>
                <th className="right">Total</th>
              </tr>
            </thead>
            <tbody>
              {rcv.map((r, i) => (
                <tr key={i}>
                  <td className="mono">{r.folio || "—"}</td>
                  <td>{r.tipo_doc || "—"}</td>
                  <td>{r.period || "—"}</td>
                  <td className="right mono">{formatMoney(r.total_amount || 0, r.currency || currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className="muted small">{result.note}</p>
    </div>
  );
}

function IntegrationResultModal({ result, onClose, onViewHistory, onSaveHistory, onNavigate }) {
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
          {result.action === "validate_rut" ? (
            <SiiResult result={result} />
          ) : (
            <>
              <div className="result-summary">
                <strong>Acción:</strong> {result.action}
                {result.query ? " · Filtro: \"" + result.query + "\"" : ""}
                {result.mode ? " · Modo: " + (result.mode === "cheapest" ? "Mejores precios" : "Todos") : ""}
                {result.order_by ? " · Orden: " + result.order_by : ""}
                {result.total !== undefined ? " · Total: " + result.total : ""}
              </div>

              {resultados.length > 0 ? (
                <div className="result-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Código</th>
                        <th>Oportunidad</th>
                        <th>Comprador</th>
                        <th>Cierre</th>
                        <th>Ítems</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultados.map((r, i) => (
                        <tr key={i}>
                          <td className="mono">{r.external_id || "—"}</td>
                          <td>{r.title || "—"}</td>
                          <td>{r.buyer || "—"}</td>
                          <td>{r.closes_at || "—"}</td>
                          <td>{r.item_count ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="muted small">{result.note || `${resultados.length} oportunidad(es) reales de Compra Ágil.`}</p>
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
              ) : (
                <div className="result-note">
                  <p>{result.note || result.mensaje || "Sin resultados para esta búsqueda."}</p>
                  {result.action === "search_items" && onNavigate ? (
                    <button
                      type="button"
                      className="button ghost"
                      onClick={() => {
                        onClose();
                        onNavigate("compra-agil");
                      }}
                    >
                      <SearchIcon /> Abrir Radar Compra Ágil para importar oportunidades
                    </button>
                  ) : null}
                </div>
              )}

              {(result.file || result.archivo || result.download_url) && (
                <div className="result-file">
                  <strong>Archivo listo:</strong> {result.filename || result.file || result.archivo}
                  <p className="muted small">{result.note || ""}</p>
                  {result.download_url && (
                    <button
                      type="button"
                      className="button primary"
                      onClick={() =>
                        downloadFile(
                          result.download_url,
                          result.filename || "exportacion_nexora.csv",
                        )
                      }
                    >
                      Descargar CSV
                    </button>
                  )}
                </div>
              )}
            </>
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

export default function NativeIntegrationsPage({ onNavigate }) {
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
            Valida RUT, revisa oportunidades reales de Compra Ágil y exporta datos a tu ERP.
            Todo funciona desde el primer día, sin configuración técnica obligatoria.
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
              <p>Buscar precios de referencia en ChileCompra y validar RUT con el algoritmo del SII.</p>
            </div>
          </div>
          <div className="context-item">
            <SuppliersIcon />
            <div>
              <strong>Proveedores</strong>
              <p>Validar RUT chileno y comparar referencias de precio por ítem.</p>
            </div>
          </div>
          <div className="context-item">
            <CheckIcon />
            <div>
              <strong>Aprobaciones</strong>
              <p>Aprobar o rechazar compras en un clic, con historial y auditoría.</p>
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
          onNavigate={onNavigate}
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
