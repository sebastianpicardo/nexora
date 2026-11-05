import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, labelize } from "../lib/format";
import {
  DownloadIcon,
  TrashIcon,
  ShieldIcon,
  ArrowLeftIcon,
  SettingsIcon,
  UsersIcon,
  AlertTriangleIcon,
} from "../components/Icons";

const ROLE_LABELS = {
  owner: "Owner",
  admin: "Admin",
  analyst: "Analista",
  user: "Usuario",
  auditor: "Auditor",
  viewer: "Solo lectura",
};

export default function SettingsPage() {
  const { user, organization, refresh } = useAuth();
  const [activeTab, setActiveTab] = useState("general");
  const [org, setOrg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [auditLog, setAuditLog] = useState({ items: [], total: 0, page: 1 });
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditPage, setAuditPage] = useState(1);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  useEffect(() => {
    if (organization) setOrg(organization);
  }, [organization]);

  async function saveSettings() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/organizations/current", {
        method: "PATCH",
        body: JSON.stringify({
          name: org?.name,
          price_spike_threshold_pct: org?.price_spike_threshold_pct,
          min_confidence: org?.min_confidence,
          default_currency: org?.default_currency,
        }),
      });
      setOrg(data);
      await refresh();
      setSuccess("Configuración guardada.");
    } catch (err) {
      setError(err.message || "No se pudo guardar.");
    } finally {
      setSaving(false);
    }
  }

  async function loadAudit(page = 1) {
    setAuditLoading(true);
    try {
      const data = await api(`/api/organizations/current/audit?page=${page}&page_size=20`);
      setAuditLog(data);
    } catch (err) {
      setError(err.message || "No se pudo cargar el log de auditoría.");
    } finally {
      setAuditLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "audit") loadAudit(auditPage);
  }, [activeTab, auditPage]);

  async function exportData() {
    setExportLoading(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/organizations/current/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nexora-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
      setSuccess("Exportación completada.");
    } catch (err) {
      setError(err.message || "No se pudo exportar.");
    } finally {
      setExportLoading(false);
    }
  }

  async function deleteOrg() {
    setError("");
    setSuccess("");
    try {
      await api(
        `/api/organizations/current?confirm=${encodeURIComponent(organization?.slug || "")}`,
        { method: "DELETE" },
      );
      setSuccess("Organización eliminada. Redirigiendo…");
      setTimeout(() => window.location.assign("/login"), 2000);
    } catch (err) {
      setError(err.message || "No se pudo eliminar.");
    }
  }

  const tabs = [
    { id: "general", label: "General", icon: SettingsIcon },
    { id: "audit", label: "Auditoría", icon: ShieldIcon },
    { id: "export", label: "Exportar datos", icon: DownloadIcon },
    { id: "danger", label: "Eliminar organización", icon: TrashIcon },
  ];

  if (!user || !organization) return null;

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><SettingsIcon /> Configuración</div>
          <h2>Organización</h2>
          <p>Gestiona los ajustes, revisa la actividad y exporta o elimina tu espacio de trabajo.</p>
        </div>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Secciones de configuración">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`settings-nav-item ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <tab.icon />
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="settings-content">
          {/* General */}
          {activeTab === "general" && (
            <section className="card">
              <h3>Información de la organización</h3>
              <div className="form-grid">
                <label className="form-field">
                  <span>Nombre</span>
                  <input
                    type="text"
                    value={org?.name || ""}
                    onChange={(e) => setOrg((o) => ({ ...o, name: e.target.value }))}
                    disabled={saving}
                  />
                </label>
                <label className="form-field">
                  <span>Slug (inmutable)</span>
                  <input type="text" value={org?.slug || ""} readOnly />
                </label>
                <label className="form-field">
                  <span>Umbral de alza de precio (%)</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={org?.price_spike_threshold_pct ?? 10}
                    onChange={(e) => setOrg((o) => ({ ...o, price_spike_threshold_pct: parseFloat(e.target.value) }))}
                    disabled={saving}
                  />
                </label>
                <label className="form-field">
                  <span>Confianza mínima de extracción</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={org?.min_confidence ?? 0.75}
                    onChange={(e) => setOrg((o) => ({ ...o, min_confidence: parseFloat(e.target.value) }))}
                    disabled={saving}
                  />
                </label>
                <label className="form-field">
                  <span>Moneda por defecto</span>
                  <select
                    value={org?.default_currency || "CLP"}
                    onChange={(e) => setOrg((o) => ({ ...o, default_currency: e.target.value }))}
                    disabled={saving}
                  >
                    <option value="CLP">CLP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="ARS">ARS</option>
                    <option value="PEN">PEN</option>
                    <option value="COP">COP</option>
                    <option value="MXN">MXN</option>
                    <option value="BRL">BRL</option>
                  </select>
                </label>
              </div>
              <div className="form-actions">
                <button type="button" className="button primary" onClick={saveSettings} disabled={saving}>
                  {saving ? "Guardando…" : "Guardar cambios"}
                </button>
              </div>
            </section>
          )}

          {/* Audit Log */}
          {activeTab === "audit" && (
            <section className="card">
              <h3>Log de auditoría</h3>
              <p className="muted">Actividad reciente de la organización (últimas 500 acciones).</p>
              {auditLoading ? (
                <div className="empty-state">Cargando…</div>
              ) : auditLog.items.length === 0 ? (
                <div className="empty-state">No hay eventos registrados.</div>
              ) : (
                <>
                  <div className="table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Acción</th>
                          <th>Entidad</th>
                          <th>Usuario</th>
                          <th>IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditLog.items.map((event) => (
                          <tr key={event.id}>
                            <td>{formatDate(event.created_at)}</td>
                            <td><span className="badge">{event.action}</span></td>
                            <td>{event.entity_type} {event.entity_id ? `#${event.entity_id.slice(0, 8)}` : ""}</td>
                            <td>{event.user_name || event.user_email || "Sistema"}</td>
                            <td className="mono">{event.ip_address || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="pagination">
                    <button
                      type="button"
                      className="button ghost"
                      disabled={auditPage <= 1}
                      onClick={() => setAuditPage((p) => p - 1)}
                    >
                      <ArrowLeftIcon /> Anterior
                    </button>
                    <span>Página {auditLog.page} de {Math.ceil(auditLog.total / 20)}</span>
                    <button
                      type="button"
                      className="button ghost"
                      disabled={auditPage >= Math.ceil(auditLog.total / 20)}
                      onClick={() => setAuditPage((p) => p + 1)}
                    >
                      Siguiente
                    </button>
                  </div>
                </>
              )}
            </section>
          )}

          {/* Export Data */}
          {activeTab === "export" && (
            <section className="card">
              <h3>Exportar todos los datos</h3>
              <p>
                Descarga un archivo JSON con toda la información de tu organización: usuarios, proveedores,
                documentos, ítems, excepciones y log de auditoría.
              </p>
              <button
                type="button"
                className="button primary"
                onClick={exportData}
                disabled={exportLoading}
              >
                {exportLoading ? "Generando…" : "Descargar JSON completo"}
                <DownloadIcon />
              </button>
            </section>
          )}

          {/* Danger Zone */}
          {activeTab === "danger" && (
            <section className="card danger-zone">
              <div className="danger-header">
                <AlertTriangleIcon />
                <div>
                  <h3>Eliminar organización</h3>
                  <p>
                    Esta acción es <strong>irreversible</strong>. Se borrarán todos los documentos, ítems,
                    proveedores, usuarios, facturas y logs de auditoría.
                  </p>
                </div>
              </div>
              {!deleteConfirm ? (
                <button type="button" className="button danger" onClick={() => setDeleteConfirm(true)}>
                  Eliminar organización
                </button>
              ) : (
                <div className="confirm-dialog">
                  <p>Escribe el slug de la organización para confirmar: <code>{organization.slug}</code></p>
                  <div className="confirm-actions">
                    <button type="button" className="button ghost" onClick={() => setDeleteConfirm(false)}>
                      Cancelar
                    </button>
                    <button type="button" className="button danger" onClick={deleteOrg}>
                      Sí, eliminar todo
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}