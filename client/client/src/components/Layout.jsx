import { useAuth } from "../context/AuthContext";
import {
  AdminIcon,
  BillingIcon,
  DashboardIcon,
  DocumentsIcon,
  ExceptionsIcon,
  LogoutIcon,
  PricesIcon,
  ProfileIcon,
  SparkIcon,
  TeamIcon,
} from "./Icons";
import { formatDate, initials, labelize, percent } from "../lib/format";

const NAV_SECTIONS = [
  {
    label: "Operación",
    items: [
      { id: "dashboard", label: "Dashboard", icon: DashboardIcon },
      { id: "documents", label: "Documentos", icon: DocumentsIcon },
      { id: "items", label: "Precios", icon: PricesIcon },
      { id: "exceptions", label: "Excepciones", icon: ExceptionsIcon },
    ],
  },
  {
    label: "Organización",
    items: [
      { id: "team", label: "Equipo", icon: TeamIcon, admin: true },
      { id: "billing", label: "Facturación", icon: BillingIcon, admin: true },
      { id: "profile", label: "Mi perfil", icon: ProfileIcon },
    ],
  },
  {
    label: "Plataforma",
    items: [{ id: "admin", label: "Super admin", icon: AdminIcon, superAdmin: true }],
  },
];

const ALL_ITEMS = NAV_SECTIONS.flatMap((section) => section.items);

export default function Layout({ active, onNavigate, children }) {
  const { user, organization, billing, canManage, isSuperAdmin, logout } = useAuth();
  const quota = billing?.usage;
  const subscription = billing?.subscription;
  const width = quota?.unlimited ? 100 : Math.min(Number(quota?.percentage) || 0, 100);
  const quotaTone = quota?.exceeded ? "danger" : quota?.warning ? "warning" : "ok";

  const sections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => {
      if (item.superAdmin) return isSuperAdmin;
      if (item.admin) return canManage;
      return true;
    }),
  })).filter((section) => section.items.length > 0);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div>
            <div className="brand-name">NEXORA</div>
            <div className="brand-sub">Compras auditadas</div>
          </div>
        </div>

        <nav className="nav">
          {sections.map((section) => (
            <div key={section.label} className="nav-section">
              <div className="nav-section-label">{section.label}</div>
              {section.items.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`nav-item ${active === item.id ? "active" : ""}`}
                    onClick={() => onNavigate(item.id)}
                  >
                    <Icon />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="plan-widget">
            <div className="plan-widget-head">
              <span><SparkIcon /> Plan {subscription?.plan_name || "Free"}</span>
              <strong>{quota?.unlimited ? "∞" : percent(width, 0)}</strong>
            </div>
            <div className="quota-track small">
              <span className={`quota-fill ${quotaTone}`} style={{ width: `${width}%` }} />
            </div>
            <div className="plan-widget-foot">
              <span>
                {quota?.unlimited
                  ? "Documentos ilimitados"
                  : `${quota?.used ?? 0} / ${quota?.limit ?? 0} documentos`}
              </span>
              {canManage ? (
                <button type="button" className="link-button" onClick={() => onNavigate("billing")}>
                  Gestionar
                </button>
              ) : null}
            </div>
            {quota?.period_end ? (
              <div className="plan-widget-cycle">Renueva {formatDate(quota.period_end)}</div>
            ) : null}
          </div>

          <div className="org-chip">
            <span className="org-dot" />
            <div>
              <div className="org-name">{organization?.name || "Mi organización"}</div>
              <div className="org-plan">
                {labelize(user?.role)} · umbral {organization?.price_spike_threshold_pct ?? 10}%
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div>
            <div className="topbar-eyebrow">Panel de control</div>
            <h1 className="topbar-title">
              {ALL_ITEMS.find((item) => item.id === active)?.label || "Dashboard"}
            </h1>
          </div>
          <div className="user-area">
            <div className="user-copy">
              <div className="user-name">{user?.name || user?.email}</div>
              <div className="user-role">{labelize(user?.role)}</div>
            </div>
            <div className="avatar">
              {user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initials(user?.name)}
            </div>
            <button type="button" className="icon-button" onClick={logout} title="Cerrar sesión">
              <LogoutIcon />
            </button>
          </div>
        </header>

        <main className="content">{children}</main>
      </div>
    </div>
  );
}
