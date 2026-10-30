import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, initials, labelize } from "../lib/format";
import { ProfileIcon, ShieldIcon } from "../components/Icons";

const TIMEZONES = [
  "America/Santiago",
  "America/Lima",
  "America/Bogota",
  "America/Mexico_City",
  "America/Argentina/Buenos_Aires",
  "UTC",
];

export default function ProfilePage() {
  const { user, organization, refresh } = useAuth();
  const [form, setForm] = useState({
    name: "",
    job_title: "",
    phone: "",
    timezone: "America/Santiago",
    notify_quota: true,
    notify_weekly: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    setForm({
      name: user?.name || "",
      job_title: user?.job_title || "",
      phone: user?.phone || "",
      timezone: user?.timezone || "America/Santiago",
      notify_quota: user?.notify_quota ?? true,
      notify_weekly: user?.notify_weekly ?? true,
    });
    setLoading(false);
  }, [user]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await api("/api/profile", {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      await refresh();
      setSuccess("Perfil actualizado.");
    } catch (err) {
      setError(err.message || "No se pudo actualizar el perfil.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="empty-state">Cargando perfil…</div>;

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><ProfileIcon /> Cuenta</div>
          <h2>Perfil y preferencias</h2>
          <p>Personaliza tu identidad dentro de NEXORA y las notificaciones que recibes.</p>
        </div>
        <span className={`badge role-${user?.role}`}>{labelize(user?.role)}</span>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="profile-grid">
        <section className="card profile-card">
          <div className="profile-hero">
            <span className="avatar xlarge">
              {user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initials(user?.name)}
            </span>
            <div>
              <h3>{user?.name || user?.email}</h3>
              <p>{user?.job_title || "Sin cargo definido"}</p>
              <span className="soft-chip">{organization?.name}</span>
            </div>
          </div>
          <div className="profile-facts">
            <div>
              <span>Email</span>
              <strong>{user?.email}</strong>
            </div>
            <div>
              <span>Organización</span>
              <strong>{organization?.name}</strong>
            </div>
            <div>
              <span>Miembro desde</span>
              <strong>{formatDate(user?.created_at)}</strong>
            </div>
            <div>
              <span>Último acceso</span>
              <strong>{formatDate(user?.last_login_at)}</strong>
            </div>
          </div>
        </section>

        <form className="card profile-form" onSubmit={submit}>
          <div className="card-head">
            <div>
              <h2>Datos personales</h2>
              <p>Tu email se administra desde la cuenta de Google.</p>
            </div>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Nombre</span>
              <input value={form.name} onChange={(event) => update("name", event.target.value)} required />
            </label>
            <label className="field">
              <span>Cargo</span>
              <input
                value={form.job_title}
                onChange={(event) => update("job_title", event.target.value)}
                placeholder="Jefe de compras"
              />
            </label>
            <label className="field">
              <span>Teléfono</span>
              <input
                value={form.phone}
                onChange={(event) => update("phone", event.target.value)}
                placeholder="+56 9 1234 5678"
              />
            </label>
            <label className="field">
              <span>Zona horaria</span>
              <select value={form.timezone} onChange={(event) => update("timezone", event.target.value)}>
                {TIMEZONES.map((timezone) => (
                  <option key={timezone} value={timezone}>
                    {timezone}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="toggle-list">
            <label className="toggle-row">
              <div>
                <strong>Alertas de cuota</strong>
                <span>Avisos cuando el consumo se acerque al límite del plan.</span>
              </div>
              <input
                type="checkbox"
                checked={form.notify_quota}
                onChange={(event) => update("notify_quota", event.target.checked)}
              />
            </label>
            <label className="toggle-row">
              <div>
                <strong>Resumen semanal</strong>
                <span>Un correo con documentos, alertas y excepciones pendientes.</span>
              </div>
              <input
                type="checkbox"
                checked={form.notify_weekly}
                onChange={(event) => update("notify_weekly", event.target.checked)}
              />
            </label>
          </div>

          <div className="form-actions">
            <span className="muted-note">
              <ShieldIcon /> Los cambios de rol se administran desde Equipo.
            </span>
            <button type="submit" className="button primary" disabled={saving}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
