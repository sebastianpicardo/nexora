import { useAuth } from "../context/AuthContext";
import { DocumentsIcon, ExceptionsIcon, PricesIcon, UploadIcon } from "../components/Icons";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import DocumentsPage from "./DocumentsPage";
import ItemsPage from "./ItemsPage";
import ExceptionsPage from "./ExceptionsPage";

const TABS = [
  { id: "documents", label: "Todos los documentos", icon: DocumentsIcon },
  { id: "items", label: "Ítems auditados", icon: PricesIcon },
  { id: "exceptions", label: "Alertas y Excepciones", icon: ExceptionsIcon },
];

const PURCHASES_INBOX_STEPS = [
  { id: 1, label: "Revisa documentos cargados" },
  { id: 2, label: "Audita precios y alertas" },
  { id: 3, label: "Resuelve excepciones" },
];

export default function PurchasesInboxPage({ tab, onTabChange, onUpload }) {
  const { canOperate } = useAuth();
  const active = TABS.some((item) => item.id === tab) ? tab : "documents";
  const STEP_BY_TAB = { documents: 1, items: 2, exceptions: 3 };
  const activeStep = STEP_BY_TAB[active] || 1;

  return (
    <div className="page-stack group-page">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Compras</div>
          <h2>Bandeja de Compras</h2>
          <p>
            Todo tu flujo documental en un solo lugar: revisa lo cargado, audita los precios y
            resuelve las alertas que requieren atención.
          </p>
        </div>
        {canOperate ? (
          <button type="button" className="button primary" onClick={onUpload}>
            <UploadIcon /> Subir documento
          </button>
        ) : null}
      </section>

      <PageTabs tabs={TABS} active={active} onChange={onTabChange} label="Bandeja de compras" />
      <QuickGuide steps={PURCHASES_INBOX_STEPS} activeStep={activeStep} />

      {active === "documents" ? (
        <DocumentsPage embedded onUpload={onUpload} />
      ) : active === "items" ? (
        <ItemsPage embedded onUpload={onUpload} />
      ) : (
        <ExceptionsPage embedded onUpload={onUpload} />
      )}
    </div>
  );
}