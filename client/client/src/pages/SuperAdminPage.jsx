import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate, formatMoney, labelize } from "../lib/format";
import StatCard from "../components/StatCard";
import { AdminIcon, DocumentsIcon, TeamIcon, ExceptionsIcon } from "../components/Icons";

export default function SuperAdminPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const response = await api("/api/admin/overview");
      setData(response);
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

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow"><AdminIcon /> Plataforma</div>
          <h2>Control multi-tenant</h2>
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
    </div>
  );
}
