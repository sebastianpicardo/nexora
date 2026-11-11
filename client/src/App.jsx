import { useEffect, useState } from "react";
import { useAuth } from "./context/AuthContext";
import { api } from "./lib/api";
import HelpChat from "./components/HelpChat";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import ItemsPage from "./pages/ItemsPage";
import ExceptionsPage from "./pages/ExceptionsPage";
import TeamPage from "./pages/TeamPage";
import ProfilePage from "./pages/ProfilePage";
import SuperAdminPage from "./pages/SuperAdminPage";
import SuppliersPage from "./pages/SuppliersPage";
import SettingsPage from "./pages/SettingsPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import EnterprisePage from "./pages/EnterprisePage";
import NativeIntegrationsPage from "./pages/NativeIntegrationsPage";
import PriceCatalogPage from "./pages/PriceCatalogPage";
import PricingPage from "./pages/PricingPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import OpportunitiesPage from "./pages/OpportunitiesPage";
import ForecastPage from "./pages/ForecastPage";
import SmartApprovalsPage from "./pages/SmartApprovalsPage";

function Splash() {
  return (
    <div className="splash">
      <div className="brand-mark large">N</div>
      <div>
        <div className="splash-title">NEXORA</div>
        <div className="splash-sub">Cargando tu espacio de trabajo…</div>
      </div>
    </div>
  );
}

export default function App() {
  const { user, loading, error, canManage, isSuperAdmin, refresh } = useAuth();
  const [view, setView] = useState("dashboard");

  useEffect(() => {
    if (!user) return;
    const params = new URLSearchParams(window.location.search);
    const token = params.get("invite");
    if (!token) return;
    api("/api/team/invitations/accept", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .catch(() => null)
      .finally(() => {
        params.delete("invite");
        const query = params.toString();
        window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
        refresh();
      });
  }, [user, refresh]);

  useEffect(() => {
    if (view === "admin" && !isSuperAdmin) setView("dashboard");
    if (["team", "billing", "settings", "enterprise", "integrations", "price-catalog"].includes(view) && !canManage) setView("dashboard");
  }, [view, isSuperAdmin, canManage]);

  if (loading) return <Splash />;
  if (!user) return <LoginPage error={error} />;

  return (
    <Layout active={view} onNavigate={setView}>
      {view === "dashboard" ? (
        <DashboardPage onNavigate={setView} />
      ) : view === "analytics" ? (
        <AnalyticsPage onNavigate={setView} />
      ) : view === "opportunities" ? (
        <OpportunitiesPage />
      ) : view === "forecast" ? (
        <ForecastPage />
      ) : view === "auto-approvals" ? (
        <SmartApprovalsPage />
      ) : view === "documents" ? (
        <DocumentsPage />
      ) : view === "items" ? (
        <ItemsPage />
      ) : view === "exceptions" ? (
        <ExceptionsPage />
      ) : view === "approvals" ? (
        <ApprovalsPage />
      ) : view === "suppliers" ? (
        <SuppliersPage />
      ) : view === "enterprise" ? (
        <EnterprisePage onNavigate={setView} />
      ) : view === "integrations" ? (
        <NativeIntegrationsPage />
      ) : view === "price-catalog" ? (
        <PriceCatalogPage />
      ) : view === "team" ? (
        <TeamPage />
      ) : view === "billing" ? (
        <PricingPage />
      ) : view === "settings" ? (
        <SettingsPage />
      ) : view === "profile" ? (
        <ProfilePage />
      ) : view === "admin" ? (
        <SuperAdminPage />
      ) : (
        <DashboardPage onNavigate={setView} />
      )}
    <HelpChat />

    </Layout>
  );
}
