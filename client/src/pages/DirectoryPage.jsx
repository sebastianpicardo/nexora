import { useAuth } from "../context/AuthContext";
import { PricesIcon, SuppliersIcon } from "../components/Icons";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import SuppliersPage from "./SuppliersPage";
import PriceCatalogPage from "./PriceCatalogPage";

const TABS = [
  { id: "suppliers", label: "Proveedores", icon: SuppliersIcon },
  { id: "catalog", label: "Catálogo propio", icon: PricesIcon, admin: true },
];

export default function DirectoryPage({ tab, onTabChange, onUpload }) {
  const { canManage } = useAuth();
  const availableTabs = TABS.filter((item) => !item.admin || canManage);
  const active = availableTabs.some((item) => item.id === tab) ? tab : "suppliers";

  return (
    <div className="page-stack group-page">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Directorio</div>
          <h2>Proveedores y catálogo</h2>
          <p>
            Mantén la base de proveedores y tu catálogo de precios alineados para comparar cada
            compra contra una referencia confiable.
          </p>
        </div>
      </section>

      <PageTabs tabs={availableTabs} active={active} onChange={onTabChange} label="Directorio" />
      <QuickGuide activeStep={2} />

      {active === "suppliers" ? (
        <SuppliersPage embedded onUpload={onUpload} />
      ) : (
        <PriceCatalogPage embedded onUpload={onUpload} />
      )}
    </div>
  );
}
