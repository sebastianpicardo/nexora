import { useEffect, useState } from "react";
import { useAuth } from "./context/AuthContext";
import { api } from "./lib/api";
import HelpChat from "./components/HelpChat";
import Layout from "./components/Layout";
import UploadModal from "./components/UploadModal";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import TeamPage from "./pages/TeamPage";
import ProfilePage from "./pages/ProfilePage";
import SuperAdminPage from "./pages/SuperAdminPage";
import SettingsPage from "./pages/SettingsPage";
import EnterprisePage from "./pages/EnterprisePage";
import NativeIntegrationsPage from "./pages/NativeIntegrationsPage";
import PricingPage from "./pages/PricingPage";
import PurchasesInboxPage from "./pages/PurchasesInboxPage";
import ApprovalsHubPage from "./pages/ApprovalsHubPage";
import IntelligencePage from "./pages/IntelligencePage";
import DirectoryPage from "./pages/DirectoryPage";
import AuditExpressPage from "./pages/AuditExpressPage";

const DEFAULT_TABS = {
  purchases: "documents",
  "approvals-hub": "smart",
  intelligence: "overview",
  directory: "suppliers",
};

const LEGACY_VIEWS = {
  documents: ["purchases", "documents"],
  items: ["purchases", "items"],
  exceptions: ["purchases", "exceptions"],
  approvals: ["approvals-hub", "manual"],
  "auto-approvals": ["approvals-hub", "smart"],
  analytics: ["intelligence", "overview"],
  opportunities: ["intelligence", "opportunities"],
  forecast: ["intelligence", "forecast"],
  suppliers: ["directory", "suppliers"],
  "price-catalog": ["directory", "catalog"],
};

const HELP_TOPICS = {
  purchases: { documents: "documents", items: "items", exceptions: "exceptions" },
  "approvals-hub": { smart: "auto-approvals", manual: "approvals" },
  intelligence: {
    overview: "analytics",
    opportunities: "opportunities",
    forecast: "forecast",
  },
  directory: { suppliers: "suppliers", catalog: "price-catalog" },
};

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
  const [tabs, setTabs] = useState(DEFAULT_TABS);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [dataVersion, setDataVersion] = useState(0);

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
    if (["admin", "backups"].includes(view) && !isSuperAdmin) setView("dashboard");
    if (["team", "billing", "settings", "enterprise", "integrations"].includes(view) && !canManage) {
      setView("dashboard");
    }
  }, [view, isSuperAdmin, canManage]);

  function navigate(next) {
    const legacy = LEGACY_VIEWS[next];
    if (legacy) {
      const [group, tab] = legacy;
      setView(group);
      setTabs((current) => ({ ...current, [group]: tab }));
      return;
    }
    setView(next);
  }

  function changeTab(group, tab) {
    setTabs((current) => ({ ...current, [group]: tab }));
  }

  function handleUploaded() {
    setDataVersion((version) => version + 1);
  }

  const helpView = HELP_TOPICS[view]?.[tabs[view]] || view;

  if (loading) return <Splash />;
  if (!user) return <LoginPage error={error} />;

  function renderView() {
    if (view === "dashboard") {
      return (
        <DashboardPage
          onNavigate={navigate}
          onUpload={() => setUploadOpen(true)}
        />
      );
    }
    if (view === "purchases") {
      return (
        <PurchasesInboxPage
          tab={tabs.purchases}
          onTabChange={(tab) => changeTab("purchases", tab)}
          onUpload={() => setUploadOpen(true)}
        />
      );
    }
    if (view === "approvals-hub") {
      return (
        <ApprovalsHubPage
          tab={tabs["approvals-hub"]}
          onTabChange={(tab) => changeTab("approvals-hub", tab)}
          onUpload={() => setUploadOpen(true)}
        />
      );
    }
    if (view === "intelligence") {
      return (
        <IntelligencePage
          tab={tabs.intelligence}
          onTabChange={(tab) => changeTab("intelligence", tab)}
          onNavigate={navigate}
          onUpload={() => setUploadOpen(true)}
        />
      );
    }
    if (view === "directory") {
      return (
        <DirectoryPage
          tab={tabs.directory}
          onTabChange={(tab) => changeTab("directory", tab)}
          onUpload={() => setUploadOpen(true)}
        />
      );
    }
    if (view === "audit-express") return <AuditExpressPage onNavigate={navigate} />;
    if (view === "enterprise") return <EnterprisePage onNavigate={navigate} />;
    if (view === "integrations") return <NativeIntegrationsPage />;
    if (view === "team") return <TeamPage />;
    if (view === "billing") return <PricingPage />;
    if (view === "settings") return <SettingsPage />;
    if (view === "profile") return <ProfilePage />;
    if (view === "admin") return <SuperAdminPage />;
    return <DashboardPage onNavigate={navigate} onUpload={() => setUploadOpen(true)} />;
  }

  return (
    <>
      <Layout active={view} onNavigate={navigate} helpView={helpView}>
        <div className="view-slot" key={`${view}-${dataVersion}`}>
          {renderView()}
        </div>
        <HelpChat />
      </Layout>
      {uploadOpen ? (
        <UploadModal
          onClose={() => setUploadOpen(false)}
          onUploaded={handleUploaded}
        />
      ) : null}
    </>
  );
}
