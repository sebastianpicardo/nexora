import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import {
  AdminIcon,
  ArrowRightIcon,
  BellIcon,
  BillingIcon,
  CheckIcon,
  DashboardIcon,
  DocumentsIcon,
  ExceptionsIcon,
  HelpIcon,
  HistoryIcon,
  LogoutIcon,
  PricesIcon,
  ProfileIcon,
  SettingsIcon,
  SparkIcon,
  SuppliersIcon,
  TeamIcon,
} from "./Icons";
import { formatDate, initials, labelize, percent } from "../lib/format";

const NAV_SECTIONS = [
  {
    label: "Inicio",
    items: [
      { id: "dashboard", label: "Resumen del día", icon: DashboardIcon },
    ],
  },
  {
    label: "Compras",
    items: [
      { id: "documents", label: "Documentos", icon: DocumentsIcon },
      { id: "items", label: "Precios auditados", icon: PricesIcon },
      { id: "exceptions", label: "Excepciones", icon: ExceptionsIcon },
      { id: "approvals", label: "Aprobaciones", icon: CheckIcon },
      { id: "suppliers", label: "Proveedores", icon: SuppliersIcon },
      { id: "price-catalog", label: "Catálogo de precios", icon: PricesIcon, admin: true },
    ],
  },
  {
    label: "Integraciones",
    items: [
      { id: "integrations", label: "ChileCompra / SII / ERP", icon: ArrowRightIcon, admin: true },
      { id: "enterprise", label: "Seguridad y marca", icon: SparkIcon, admin: true },
      { id: "backups", label: "Backups", icon: HistoryIcon, admin: true },
    ],
  },
  {
    label: "Administración",
    items: [
      { id: "team", label: "Equipo", icon: TeamIcon, admin: true },
      { id: "billing", label: "Facturación y plan", icon: BillingIcon, admin: true },
      { id: "settings", label: "Configuración", icon: SettingsIcon, admin: true },
      { id: "profile", label: "Mi perfil", icon: ProfileIcon },
    ],
  },
  {
    label: "Plataforma",
    items: [{ id: "admin", label: "Usuarios y auditoría", icon: AdminIcon, superAdmin: true }],
  },
];

const ALL_ITEMS = NAV_SECTIONS.flatMap((section) => section.items);

export default function Layout({ active, onNavigate, children }) {
  const { user, organization, billing, branding, canManage, isSuperAdmin, logout } = useAuth();
  const [summary, setSummary] = useState(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notificationRef = useRef(null);
  const quota = billing?.usage;
  const subscription = billing?.subscription;
  const width = quota?.unlimited ? 100 : Math.min(Number(quota?.percentage) || 0, 100);
  const quotaTone = quota?.exceeded ? "danger" : quota?.warning ? "warning" : "ok";

  useEffect(() => {
    let cancelled = false;
    api("/api/dashboard/summary")
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [active]);

  useEffect(() => {
    function handleClick(event) {
      if (notificationRef.current && !notificationRef.current.contains(event.target)) {
        setNotificationsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const notifications = [];
  if (quota?.exceeded) {
    notifications.push({
      id: "quota-exceeded",
      tone: "danger",
      title: "Límite de documentos alcanzado",
      body: "Actualiza tu plan para seguir cargando archivos.",
      action: "billing",
    });
  } else if (quota?.warning) {
    notifications.push({
      id: "quota-warning",
      tone: "warning",
      title: "Estás cerca del límite mensual",
      body: `Usaste ${quota.used}/${quota.limit} documentos de tu plan.`,
      action: "billing",
    });
  }
  if (summary?.documents_pending) {
    notifications.push({
      id: "documents-pending",
      tone: "info",
      title: `${summary.documents_pending} documento(s) en proceso`,
      body: "La extracción continúa en segundo plano.",
      action: "documents",
    });
  }
  if (summary?.exceptions_pending) {
    notifications.push({
      id: "exceptions-pending",
      tone: "warning",
      title: `${summary.exceptions_pending} excepción(es) pendientes`,
      body: "Revisa la bandeja para aprobar o corregir.",
      action: "exceptions",
    });
  }
  if (quota?.period_end) {
    notifications.push({
      id: "period-end",
      tone: "info",
      title: "Renovación de plan",
      body: `Tu período actual termina el ${formatDate(quota.period_end)}.`,
      action: "billing",
    });
  }

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
          <div className="brand-mark">
            {branding?.logo_url ? <img src={branding.logo_url} alt="" /> : (branding?.brand_name || "N").slice(0, 1)}
          </div>
          <div>
            <div className="brand-name">{branding?.brand_name || "NEXORA"}</div>
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
              {ALL_ITEMS.find((item) => item.id === active)?.label || "Resumen del día"}
            </h1>
          </div>
          <div className="user-area">
            <div className="notification-area" ref={notificationRef}>
              <button
                type="button"
                className={`icon-button notification-button ${notificationsOpen ? "active" : ""}`}
                title="Notificaciones"
                aria-label="Notificaciones"
                aria-expanded={notificationsOpen}
                onClick={() => setNotificationsOpen((value) => !value)}
              >
                <BellIcon />
                {notifications.length > 0 ? (
                  <span className="notification-badge">{notifications.length}</span>
                ) : null}
              </button>
              {notificationsOpen ? (
                <div className="notification-panel" role="menu">
                  <div className="notification-panel-head">
                    <strong>Notificaciones</strong>
                    <span>{notifications.length}</span>
                  </div>
                  {notifications.length === 0 ? (
                    <div className="notification-empty">Todo al día. No tienes alertas nuevas.</div>
                  ) : (
                    notifications.map((notification) => (
                      <button
                        key={notification.id}
                        type="button"
                        role="menuitem"
                        className="notification-item"
                        onClick={() => {
                          onNavigate(notification.action);
                          setNotificationsOpen(false);
                        }}
                      >
                        <span className={`notification-dot ${notification.tone || ""}`} />
                        <span className="notification-copy">
                          <strong>{notification.title}</strong>
                          <small>{notification.body}</small>
                        </span>
                      </button>
                    ))
                  )}
                </div>
              ) : null}
            </div>
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
