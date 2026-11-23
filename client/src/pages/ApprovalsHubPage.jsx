import { CheckIcon, ClockIcon } from "../components/Icons";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import SmartApprovalsPage from "./SmartApprovalsPage";
import ApprovalsPage from "./ApprovalsPage";

const APPROVALS_HUB_STEPS = [
  { id: 1, label: "Revisa solicitudes pendientes" },
  { id: 2, label: "Aprobar o rechazar" },
  { id: 3, label: "Notifica al solicitante" },
];

export default function ApprovalsHubPage({ tab, onTabChange, onUpload }) {
  const active = TABS.some((item) => item.id === tab) ? tab : "smart";

  return (
    <div className="page-stack group-page">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Gobierno de compras</div>
          <h2>Aprobaciones</h2>
          <p>
            Aprueba primero lo seguro y concentra tu atención en las compras que realmente
            necesitan una decisión manual.
          </p>
        </div>
      </section>

      <PageTabs tabs={TABS} active={active} onChange={onTabChange} label="Aprobaciones" />
      <QuickGuide steps={APPROVALS_HUB_STEPS} activeStep={3} />

      {active === "smart" ? (
        <SmartApprovalsPage embedded onUpload={onUpload} />
      ) : (
        <ApprovalsPage embedded />
      )}
    </div>
  );
}