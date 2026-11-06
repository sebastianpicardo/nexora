import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate, formatMoney, labelize } from "../lib/format";
import StatCard from "../components/StatCard";
import { AdminIcon, DocumentsIcon, TeamIcon, ExceptionsIcon, TrashIcon, XIcon, CheckIcon } from "../components/Icons";
import InfoHint from "../components/InfoHint";

export default function SuperAdminPage() {
  const [data, setData] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState({ role: "", active: true });
  const [deletingId, setDeletingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [overviewData, usersData] = await Promise.all([
        api("/api/admin/overview"),
        api("/api/admin/users"),
      ]);
      setData(overviewData);
      setUsers(usersData.users || []);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudo cargar el panel global.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = data?.stats;

  function openEdit(user) {
    setEditingUser(user);
    setEditForm({ role: user.role, active: user.active });
  }

  function closeEdit() {
    setEditingUser(null);
    setEditForm({ role: "", active: true });
  }

  async function saveEdit() {
    setSaving(true);
    setError("");
    try {
      await api(`/api/admin/users/${editingUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({ role: editForm.role, active: editForm.active }),
      });
      closeEdit();
      setSaving(false);
      load();
    } catch (err) {
      setError(err.message || "No se pudo actualizar el usuario.");
      setSaving(false);
    }
  }

  function confirmDelete(userId) {
    setDeletingId(userId);
  }

  async function executeDelete() {
    if (!deletingId) return;
    setRemoving(true);
    setError("");
    try {
      await api(`/api/admin/users/${deletingId}`, { method: "DELETE" });
      setRemoving(false);
      setDeletingId(null);
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar el usuario.");
      setRemoving(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><AdminIcon /> Plataforma</div>
          <h2>Control multi-tenant
            <InfoHint title="Panel de super administrador">
              Desde aquí puedes ver todas las organizaciones, sus planes y consumo. También gestionar usuarios de la
              plataforma: cambiar rol, activar/desactivar cuentas y eliminar usuarios.
            </InfoHint>
          </h2>
          <p>Vista global de organizaciones, consumo, planes y excepciones de toda la plataforma.</p>
        </div>
        <button type="button" className="button ghost" onClick={load}>
          Actualizar
        </button>
      </section>

      {error ? <div className="alert error">{error}</div> : null}

      <section className="stats-grid">
        <StatCard
          label="Organizaciones"
          value={loading ? "—" : stats?.organizations_total ?? 0}
          detail="Tenants activos"
          tone="brand"
          icon={<AdminIcon />}
        />
        <StatCard
          label="Usuarios"
          value={loading ? "—" : stats?.users_total ?? 0}
          detail="Cuentas activas"
          icon={<TeamIcon />}
        />
        <StatCard
          label="Documentos del mes"
          value={loading ? "—" : stats?.documents_month ?? 0}
          detail={`${stats?.documents_total ?? 0} históricos`}
          tone="warning"
          icon={<DocumentsIcon />}
        />
        <StatCard
          label="MRR"
          value={loading ? "—" : formatMoney(stats?.mrr ?? 0, "USD")}
          detail={`${stats?.exceptions_pending ?? 0} excepciones pendientes`}
          icon={<ExceptionsIcon />}
        />
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Organizaciones</h2>
            <p>Consumo del ciclo actual y estado de suscripción.</p>
          </div>
          <span className="counter-chip">{data?.organizations?.length ?? 0} tenants</span>
        </div>

        {loading ? (
          <div className="empty-state">Cargando organizaciones…</div>
        ) : data?.organizations?.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Organización</th>
                  <th>Plan</th>
                  <th>Usuarios</th>
                  <th>Docs. mes</th>
                  <th>Docs. total</th>
                  <th>Excepciones</th>
                  <th>Creada</th>
                </tr>
              </thead>
              <tbody>
                {data.organizations.map((org) => (
                  <tr key={org.id}>
                    <td>
                      <div className="cell-title">{org.name}</div>
                      <div className="cell-sub">{org.slug}</div>
                    </td>
                    <td>
                      <span className={`badge plan-${org.plan_id}`}>{org.plan_name}</span>
                      <div className="cell-sub">{labelize(org.subscription_status)}</div>
                    </td>
                    <td>{org.users_total}</td>
                    <td>{org.documents_month}</td>
                    <td>{org.documents_total}</td>
                    <td>{org.exceptions_pending}</td>
                    <td>{formatDate(org.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">Todavía no hay organizaciones registradas.</div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Usuarios de la plataforma</h2>
            <p>Gestionar cuentas: cambiar rol, activar/desactivar o eliminar.</p>
          </div>
        </div>

        {loading ? (
          <div className="empty-state">Cargando usuarios…</div>
        ) : users.length === 0 ? (
          <div className="empty-state">No hay usuarios registrados.</div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Email</th>
                  <th>Organización</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Último acceso</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="cell-title">{u.name || u.email}</div>
                    </td>
                    <td className="mono">{u.email}</td>
                    <td>{u.org_name || "—"}</td>
                    <td>
                      <span className={`badge role-${u.role}`}>{labelize(u.role)}</span>
                    </td>
                    <td>
                      <span className={`badge ${u.active ? "status-active" : "status-inactive"}`}>
                        {u.active ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td>{u.last_login_at ? formatDate(u.last_login_at) : "—"}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => openEdit(u)}
                          title="Editar rol y estado"
                        >
                          <CheckIcon />
                        </button>
                        {u.active ? (
                          <button
                            type="button"
                            className="button ghost icon-only danger"
                            onClick={() => confirmDelete(u.id)}
                            title="Eliminar usuario"
                          >
                            <TrashIcon />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Edit modal */}
        {editingUser && (
          <div className="modal-overlay" onClick={closeEdit}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-head">
                <h3>Editar usuario</h3>
                <button type="button" className="icon-button" onClick={closeEdit}>
                  <XIcon />
                </button>
              </div>
              <div className="modal-body">
                {error && <div className="alert error">{error}</div>}
                <label className="form-field">
                  <span>Nombre</span>
                  <input value={editingUser.name || ""} readOnly />
                </label>
                <label className="form-field">
                  <span>Email</span>
                  <input value={editingUser.email} readOnly />
                </label>
                <label className="form-field">
                  <span>Organización</span>
                  <input value={editingUser.org_name || "—"} readOnly />
                </label>
                <label className="form-field">
                  <span>Rol</span>
                  <select
                    value={editForm.role}
                    onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  >
                    <option value="super_admin">Super admin</option>
                    <option value="owner">Propietario</option>
                    <option value="admin">Administrador</option>
                    <option value="analyst">Analista</option>
                    <option value="user">Usuario</option>
                    <option value="viewer">Auditor</option>
                  </select>
                </label>
                <label className="form-field checkbox-field">
                  <input
                    type="checkbox"
                    checked={editForm.active}
                    onChange={(e) => setEditForm({ ...editForm, active: e.target.checked })}
                  />
                  <span>Usuario activo</span>
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="button ghost" onClick={closeEdit} disabled={saving}>
                  Cancelar
                </button>
                <button type="button" className="button primary" onClick={saveEdit} disabled={saving}>
                  {saving ? "Guardando…" : "Guardar cambios"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete modal */}
        {deletingId && (
          <div className="modal-overlay" onClick={() => setDeletingId(null)}>
            <div className="modal danger" onClick={(e) => e.stopPropagation()}>
              <div className="modal-head">
                <h3>Eliminar usuario</h3>
              </div>
              <div className="modal-body">
                <p>¿Eliminar este usuario? Esta acción no se puede deshacer.</p>
                <p className="muted">Los documentos y auditoría del usuario quedarán asociados a su organización.</p>
              </div>
              <div className="modal-actions">
                <button type="button" className="button ghost" onClick={() => setDeletingId(null)} disabled={removing}>
                  Cancelar
                </button>
                <button type="button" className="button danger" onClick={executeDelete} disabled={removing}>
                  {removing ? "Eliminando…" : "Sí, eliminar"}
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
