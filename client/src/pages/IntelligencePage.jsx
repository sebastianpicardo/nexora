import { ClockIcon, DollarIcon, PricesIcon, SearchIcon, SparkIcon } from "../components/Icons";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import AnalyticsPage from "./AnalyticsPage";
import OpportunitiesPage from "./OpportunitiesPage";
import ForecastPage from "./ForecastPage";
import MarginGuardianPanel from "../components/MarginGuardianPanel";
import PurchaseOptimizerPanel from "../components/PurchaseOptimizerPanel";
import CompraAgilPanel from "../components/CompraAgilPanel";

const TABS = [
  { id: "overview", label: "Panorama", icon: SparkIcon },
  { id: "opportunities", label: "Oportunidades y ahorro verificado", icon: DollarIcon },
  { id: "margin", label: "Guardián de margen", icon: PricesIcon },
  { id: "compare", label: "Comparador y compra óptima", icon: SearchIcon },
  { id: "compra-agil", label: "Radar Compra Ágil", icon: SearchIcon },
  { id: "forecast", label: "Pronóstico", icon: ClockIcon },
];

export default function IntelligencePage({ tab, onTabChange, onNavigate, onUpload }) {
  const active = TABS.some((item) => item.id === tab) ? tab : "overview";

  return (
    <div className="page-stack group-page">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Inteligencia y Ahorro</div>
          <h2>Convierte tus datos en decisiones</h2>
          <p>
            Detecta sobreprecios, entiende la evolución de tus compras y anticipa el próximo
            período con una vista ejecutiva.
          </p>
        </div>
      </section>

      <PageTabs tabs={TABS} active={active} onChange={onTabChange} label="Inteligencia y ahorro" />
      <QuickGuide activeStep={2} />

      {active === "overview" ? (
        <AnalyticsPage embedded onNavigate={onNavigate} onUpload={onUpload} />
      ) : active === "opportunities" ? (
        <OpportunitiesPage embedded onUpload={onUpload} />
      ) : active === "margin" ? (
        <MarginGuardianPanel />
      ) : active === "compare" ? (
        <PurchaseOptimizerPanel />
      ) : active === "compra-agil" ? (
        <CompraAgilPanel />
      ) : (
        <ForecastPage embedded onUpload={onUpload} />
      )}
    </div>
  );
}
