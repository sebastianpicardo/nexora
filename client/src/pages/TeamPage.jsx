import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDateTime, initials, labelize } from "../lib/format";
import { CheckIcon, CopyIcon, TeamIcon } from "../components/Icons";

const ROLE_OPTIONS = [
  { value: "admin", label: "Administrador", hint: "Equipo, facturación, configuración y toda la operación." },
  { value: "analyst", label: "Analista", hint: "Analiza precios, oportunidades y reportes." },
  { value: "user", label: "Usuario", hint: "Carga documentos, revisa excepciones y exporta reportes." },
  { value: "auditor", label: "Auditor", hint: "Solo lectura de precios, excepciones y exportaciones." },
  { value: "viewer", label: "Visor", hint: "Acceso de solo lectura al dashboard." },
];

function membersLabel(count) {
  return `${count} miembro${count === 1 ? "" : "s"}`;
}

export default function TeamPage({ onNavigate }) {
  const { user, canManage } = useAuth();
  const [team, setTeam] = useState({ members: [], invitations: [], permissions: {}, usage: null });
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [lastInvite, setLastInvite] = useState(null);

  const usage = team.usage || {};
  const atLimit = Boolean(usage.at_limit) && !usage.unlimited;
  const usedSeats = (usage.members_active || 0) + (usage.invitations_pending || 0);
  const userLimit = usage.user_limit;
  const roleHint = ROLE_OPTIONS.find((option) => option.value === role)?.hint || "";

  const load = useCallback(async () => {
    try {
      const data = await api("/api/team");
      setTeam(data);
      setError("");
    } catch (err) {
      setError(err.message || "No se pudo cargar el equipo.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function invite(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const data = await api("/api/team/invitations", {
        method: "POST",
        body: JSON.stringify({ email, role }),
      });
      setEmail("");
      setLastInvite(data);
      setSuccess("Invitación creada. Copia el enlace y compártelo con la persona.");
      await load();
    } catch (err) {
      setError(err.message || "No se pudo invitar al miembro.");
    } finally {
      setSubmitting(false);
    }
  }

  async function updateMember(member, patch) {
    setError("");
    setSuccess("");
    try {
      await api(`/api/team/members/${member.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setSuccess("Miembro actualizado.");
      await load();
    } catch (err) {
      setError(err.message || "No se pudo actualizar al miembro.");
    }
  }

  async function revoke(invitation) {
    setError("");
    try {
      await api(`/api/team/invitations/${invitation.id}`, { method: "DELETE" });
      if (lastInvite?.id === invitation.id) setLastInvite(null);
      await load();
    } catch (err) {
      setError(err.message || "No se pudo revocar la invitación.");
    }
  }

  async function copyInvite(url) {
    try {
      await navigator.clipboard.writeText(url);
      setSuccess("Enlace copiado.");
    } catch {
      setSuccess(`Enlace: ${url}`);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><TeamIcon /> Organización</div>
          <h2>Equipo y accesos</h2>
          <p>Invita a tu equipo y define quién administra, opera o audita la información de compras.</p>
        </div>
        <span className="counter-chip">
          {membersLabel(usage.members_active ?? team.members.length)}
          {usage.unlimited ? " · usuarios ilimitados" : userLimit != null ? ` · cupo ${userLimit}` : ""}
        </span>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      {canManage && (usage.unlimited || usage.user_limit != null) ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Uso del plan</h2>
              <p>
                {usage.plan_name ? `Plan ${usage.plan_name} · ` : ""}
                {usage.members_active || 0} activo(s) + {usage.invitations_pending || 0} invitación(es) pendiente(s)
              </p>
            </div>
            <button type="button" className="button ghost small" onClick={() => onNavigate?.("billing")}>
              {atLimit ? "Mejorar plan" : "Ver planes"}
            </button>
          </div>
          {usage.unlimited ? (
            <p className="muted small">Tu plan permite usuarios ilimitados.</p>
          ) : (
            <>
              <div className="quota-track">
                <span
                  className={`quota-fill ${atLimit ? "danger" : usedSeats >= Math.max(1, (userLimit || 1) - 1) ? "warning" : "ok"}`}
                  style={{ width: `${Math.min(100, userLimit ? (usedSeats / userLimit) * 100 : 0)}%` }}
                />
              </div>
              <p className="muted small">
                {usedSeats} de {userLimit} usuarios en uso (incluye invitaciones pendientes).
              </p>
            </>
          )}
        </section>
      ) : null}

      {canManage ? (
        <section className="card invite-card">
          <div className="card-head">
            <div>
              <h2>Invitar miembro</h2>
              <p>La persona recibe acceso con su cuenta de Google y el rol asignado.</p>
            </div>
          </div>
          {atLimit ? (
            <div className="alert warning">
              <span>
                Alcanzaste el límite de {userLimit} usuario(s) de tu plan
                {usage.plan_name ? ` ${usage.plan_name}` : ""}. Actualiza tu plan para invitar a más
                personas.
              </span>
              <button type="button" className="button primary small" onClick={() => onNavigate?.("billing")}>
                Ir a Planes y precios
              </button>
            </div>
          ) : null}
          <form className="invite-form" onSubmit={invite}>
            <label className="field">
              <span>Email corporativo</span>
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="nombre@empresa.com"
              />
            </label>
            <label className="field">
              <span>Rol</span>
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {roleHint ? <p className="muted small">{roleHint}</p> : null}
            </label>
            <button type="submit" className="button primary" disabled={submitting || atLimit}>
              {submitting ? "Invitando…" : "Generar invitación"}
            </button>
          </form>
          {lastInvite ? (
            <div className="invite-link-box">
              <div>
                <span>Enlace de invitación para {lastInvite.email}</span>
                <code>{lastInvite.invite_url}</code>
              </div>
              <button type="button" className="button ghost small" onClick={() => copyInvite(lastInvite.invite_url)}>
                <CopyIcon /> Copiar
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Miembros</h2>
            <p>Roles activos dentro de tu organización.</p>
          </div>
        </div>
        {loading ? (
          <div className="empty-state">Cargando equipo…</div>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Miembro</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Último acceso</th>
                  {canManage ? <th className="right">Acciones</th> : null}
                </tr>
              </thead>
              <tbody>
                {team.members.map((member) => {
                  const isSelf = member.id === user?.id;
                  const protectedMember = ["owner", "super_admin"].includes(member.role);
                  const canEdit = canManage && !isSelf && (!protectedMember || user?.role === "super_admin");
                  return (
                    <tr key={member.id}>
                      <td>
                        <div className="member-cell">
                          <span className="avatar small">
                            {member.avatar_url ? <img src={member.avatar_url} alt="" /> : initials(member.name)}
                          </span>
                          <div>
                            <div className="cell-title">
                              {member.name || member.email} {isSelf ? <span className="soft-chip">Tú</span> : null}
                            </div>
                            <div className="cell-sub">{member.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        {canEdit ? (
                          <select
                            className="inline-select"
                            value={member.role}
                            onChange={(event) => updateMember(member, { role: event.target.value })}
                          >
                            {member.role === "owner" || member.role === "super_admin" ? (
                              <option value={member.role}>{labelize(member.role)}</option>
                            ) : null}
                            {ROLE_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={`badge role-${member.role}`}>{labelize(member.role)}</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${member.active ? "status-processed" : "status-rejected"}`}>
                          {member.active ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td>{member.last_login_at ? formatDateTime(member.last_login_at) : "Nunca"}</td>
                      {canManage ? (
                        <td className="right">
                          {canEdit && member.active ? (
                            <button
                              type="button"
                              className="button ghost small"
                              onClick={() => updateMember(member, { active: false })}
                            >
                              Desactivar
                            </button>
                          ) : canEdit && !member.active ? (
                            <button
                              type="button"
                              className="button ghost small"
                              onClick={() => updateMember(member, { active: true })}
                            >
                              Reactivar
                            </button>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Invitaciones pendientes</h2>
            <p>Enlaces activos por 14 días.</p>
          </div>
        </div>
        {team.invitations.length === 0 ? (
          <div className="empty-state">No hay invitaciones pendientes.</div>
        ) : (
          <div className="invite-list">
            {team.invitations.map((invitation) => (
              <div key={invitation.id} className="invite-row">
                <div>
                  <strong>{invitation.email}</strong>
                  <span>
                    {labelize(invitation.role)} · vence {formatDateTime(invitation.expires_at)}
                  </span>
                </div>
                <div className="invite-row-actions">
                  <button
                    type="button"
                    className="button ghost small"
                    onClick={() => copyInvite(invitation.invite_url)}
                  >
                    <CopyIcon /> Copiar enlace
                  </button>
                  {canManage ? (
                    <button type="button" className="button ghost small danger" onClick={() => revoke(invitation)}>
                      Revocar
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card role-guide">
        <div className="card-head">
          <div>
            <h2>Permisos por rol</h2>
            <p>Una separación simple entre administración, operación y auditoría.</p>
          </div>
        </div>
        <div className="role-grid">
          <div>
            <span className="badge role-admin">Administrador</span>
            <p>Equipo, facturación, configuración y toda la operación.</p>
          </div>
          <div>
            <span className="badge role-user">Usuario</span>
            <p>Carga documentos, revisa excepciones y exporta reportes.</p>
          </div>
          <div>
            <span className="badge role-auditor">Auditor</span>
            <p>Lectura de precios, excepciones y exportaciones.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
