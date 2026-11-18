import { ClockIcon, DollarIcon, SparkIcon } from "../components/Icons";
import PageTabs from "../components/PageTabs";
import QuickGuide from "../components/QuickGuide";
import AnalyticsPage from "./AnalyticsPage";
import OpportunitiesPage from "./OpportunitiesPage";
import ForecastPage from "./ForecastPage";

const TABS = [
  { id: "overview", label: "Panorama", icon: SparkIcon },
  { id: "opportunities", label: "Oportunidades de ahorro", icon: DollarIcon },
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
      ) : (
        <ForecastPage embedded onUpload={onUpload} />
      )}
    </div>
  );
}
