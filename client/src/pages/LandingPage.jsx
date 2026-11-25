import { useMemo, useState } from "react";
import { formatMoney } from "../lib/format";
import PricingTable from "../components/PricingTable";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockIcon,
  DocumentsIcon,
  HistoryIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
  TrendDownIcon,
  TrendUpIcon,
} from "../components/Icons";

const INTEGRATIONS = [
  "SII · RCV",
  "Compra Ágil",
  "Facturas electrónicas",
  "Excel / CSV",
  "Tu ERP",
];

const PAIN_POINTS = [
  {
    icon: TrendDownIcon,
    title: "Pagas de más sin notarlo",
    text: "Los precios suben entre una compra y otra y nadie los compara contra tu histórico.",
  },
  {
    icon: AlertTriangleIcon,
    title: "Apruebas facturas con diferencias",
    text: "Totales que no cuadran con la orden de compra o con el RCV, y se pagan igual.",
  },
  {
    icon: ClockIcon,
    title: "Pierdes horas en planillas",
    text: "Miles de líneas revisadas a mano: lento, cansador y fácil de dejar pasar.",
  },
  {
    icon: SearchIcon,
    title: "Compras sin comparar",
    text: "El proveedor de siempre no siempre es el más conveniente. Sin datos, no lo sabes.",
  },
];

const OUTCOMES = [
  {
    icon: AlertTriangleIcon,
    title: "Detectas sobrecostos con evidencia",
    text: "Cada diferencia queda documentada con precio, proveedor y referencia.",
  },
  {
    icon: DocumentsIcon,
    title: "Validas facturas contra RCV y OC",
    text: "Alertas cuando un total, una cantidad o una unidad no coinciden.",
  },
  {
    icon: ClockIcon,
    title: "Revisas en minutos, no en días",
    text: "Excepciones priorizadas por impacto para decidir primero lo que más pesa.",
  },
  {
    icon: TrendUpIcon,
    title: "Negocias con datos",
    text: "Comparas proveedores y llegas a la mesa con números, no con intuición.",
  },
];

const FEATURES = [
  {
    icon: AlertTriangleIcon,
    title: "Detección de sobrecostos",
    text: "Alzas de precio frente al histórico de cada proveedor e ítem, con la evidencia a la vista.",
  },
  {
    icon: DocumentsIcon,
    title: "Auditoría de facturas y RCV",
    text: "Cruza facturas, órdenes de compra y RCV para encontrar diferencias, faltantes y duplicados.",
  },
  {
    icon: TrendUpIcon,
    title: "Control de margen",
    text: "Ve cómo el costo de compra presiona tu margen antes de que el daño sea irreversible.",
  },
  {
    icon: SearchIcon,
    title: "Comparador de proveedores",
    text: "Mismo producto, distintos precios: elige con información real y no por costumbre.",
  },
  {
    icon: ShieldIcon,
    title: "Aprobaciones con respaldo",
    text: "Cada aprobación queda con evidencia y trazabilidad, lista para auditar después.",
  },
  {
    icon: SparkIcon,
    title: "Ahorro medible",
    text: "Cuantifica el ahorro detectado y recuperado, mes a mes, para mostrarlo con números.",
  },
];

const STEPS = [
  {
    title: "Sube o conecta",
    text: "Arrastra facturas, cotizaciones y listas de precios, o conecta el RCV del SII y Compra Ágil.",
  },
  {
    title: "NEXORA audita",
    text: "Normaliza unidades y monedas, cruza contra tu histórico y detecta alzas, errores y diferencias.",
  },
  {
    title: "Decide y ahorra",
    text: "Revisa excepciones con evidencia, aprueba con un clic y mide cuánto recuperaste.",
  },
];

const FAQS = [
  {
    q: "¿Necesito integrar mi ERP para empezar?",
    a: "No. Puedes empezar subiendo facturas, cotizaciones o planillas en Excel/CSV. Si usas el RCV del SII o Compra Ágil, también puedes conectarlos para automatizar la carga.",
  },
  {
    q: "¿Es seguro subir mis facturas y datos de compra?",
    a: "Sí. La información queda aislada por organización, con roles y permisos por usuario. No compartimos tus datos con terceros ni los usamos para otros fines.",
  },
  {
    q: "¿Reemplaza a mi contador o a mi ERP?",
    a: "No. NEXORA los complementa: audita, prioriza y documenta las diferencias para que tú y tu equipo decidan más rápido y con respaldo.",
  },
  {
    q: "¿Cuánto demora en mostrar resultados?",
    a: "Los primeros hallazgos aparecen en minutos después de subir tus documentos. Mientras más histórico cargues, más precisa es la detección de alzas y patrones.",
  },
  {
    q: "¿Necesito tarjeta de crédito para probar?",
    a: "No. El plan gratuito no pide tarjeta y te permite auditar tus primeras compras para que veas el valor antes de decidir.",
  },
  {
    q: "¿Sirve para una pyme pequeña?",
    a: "Sí. Está pensado para pymes, ferreterías y distribuidoras que compran todos los meses y no tienen un equipo dedicado a auditar cada factura.",
  },
];

const HERO_FINDINGS = [
  {
    label: "Ferretería Andina · Tornillos 1/4″",
    note: "+18% vs. histórico",
    amount: 420000,
    tone: "danger",
  },
  {
    label: "Factura N° 8421",
    note: "Total no coincide con RCV",
    amount: 96300,
    tone: "danger",
  },
  {
    label: "Compra Ágil N° 2291",
    note: "Mejor precio alternativo",
    amount: 768200,
    tone: "ok",
  },
];

const HERO_TOTAL = HERO_FINDINGS.reduce((sum, item) => sum + item.amount, 0);
const BAR_HEIGHTS = [38, 54, 44, 68, 58, 82, 72];

function HeroPanel() {
  return (
    <div className="landing-hero-visual">
      <div className="landing-panel" role="img" aria-label="Ejemplo de auditoría con ahorro detectado">
        <div className="landing-panel-head">
          <div>
            <span className="landing-panel-kicker">Auditoría de marzo</span>
            <strong className="landing-panel-title">Panel de ahorro</strong>
          </div>
          <span className="landing-demo-badge">Ejemplo</span>
        </div>

        <div className="landing-savings">
          <span className="landing-savings-label">Ahorro detectado</span>
          <strong className="landing-savings-value">{formatMoney(HERO_TOTAL)}</strong>
          <span className="landing-savings-note">3 hallazgos que antes pasaban desapercibidos</span>
        </div>

        <div className="landing-mini-bars" aria-hidden="true">
          {BAR_HEIGHTS.map((height, index) => (
            <span
              key={index}
              className={`landing-bar ${index === BAR_HEIGHTS.length - 1 ? "is-peak" : ""}`}
              style={{ height: `${height}%` }}
            />
          ))}
        </div>

        <ul className="landing-finding-list">
          {HERO_FINDINGS.map((item) => (
            <li key={item.label} className={`landing-finding is-${item.tone}`}>
              <span className="landing-finding-dot" aria-hidden="true" />
              <div className="landing-finding-copy">
                <span className="landing-finding-label">{item.label}</span>
                <span className="landing-finding-note">{item.note}</span>
              </div>
              <strong className="landing-finding-amount">{formatMoney(item.amount)}</strong>
            </li>
          ))}
        </ul>
      </div>

      <div className="landing-float landing-float-top" aria-hidden="true">
        <ShieldIcon />
        <span>Datos aislados por empresa</span>
      </div>
      <div className="landing-float landing-float-bottom" aria-hidden="true">
        <CheckIcon />
        <span>Listo en minutos</span>
      </div>
    </div>
  );
}

function SavingsCalculator({ onStart }) {
  const [monthly, setMonthly] = useState(50000000);
  const [overcost, setOvercost] = useState(3);

  const { annual, quarter } = useMemo(() => {
    const base = monthly * (overcost / 100);
    return {
      annual: Math.round(base * 12),
      quarter: Math.round(base * 3),
    };
  }, [monthly, overcost]);

  return (
    <section className="landing-section landing-calc-section" id="ahorro">
      <div className="landing-container landing-calc">
        <div className="landing-calc-copy">
          <span className="landing-pill">Calculadora de ahorro</span>
          <h2 className="landing-h2">¿Cuánto margen estás regalando cada mes?</h2>
          <p className="landing-section-sub">
            Ajusta tus compras mensuales y un sobrecosto conservador. Es una estimación
            referencial: NEXORA te muestra las diferencias reales, con evidencia.
          </p>

          <div className="landing-calc-field">
            <div className="landing-calc-label">
              <label htmlFor="calc-monthly">Compras mensuales</label>
              <strong>{formatMoney(monthly)}</strong>
            </div>
            <input
              id="calc-monthly"
              type="range"
              min={5000000}
              max={200000000}
              step={1000000}
              value={monthly}
              onChange={(event) => setMonthly(Number(event.target.value))}
              aria-valuetext={formatMoney(monthly)}
            />
            <div className="landing-calc-scale">
              <span>{formatMoney(5000000)}</span>
              <span>{formatMoney(200000000)}</span>
            </div>
          </div>

          <div className="landing-calc-field">
            <div className="landing-calc-label">
              <label htmlFor="calc-overcost">Sobrecosto estimado</label>
              <strong>{overcost.toLocaleString("es-CL", { maximumFractionDigits: 1 })}%</strong>
            </div>
            <input
              id="calc-overcost"
              type="range"
              min={0.5}
              max={10}
              step={0.5}
              value={overcost}
              onChange={(event) => setOvercost(Number(event.target.value))}
              aria-valuetext={`${overcost} por ciento`}
            />
            <div className="landing-calc-scale">
              <span>0,5%</span>
              <span>10%</span>
            </div>
          </div>
        </div>

        <div className="landing-calc-result">
          <span className="landing-result-kicker">Ahorro potencial al año</span>
          <strong className="landing-result-value">{formatMoney(annual)}</strong>
          <span className="landing-result-sub">
            Cerca de <b>{formatMoney(quarter)}</b> en los próximos 90 días.
          </span>

          <ul className="landing-result-list">
            <li>
              <CheckIcon />
              <span>Detección de alzas contra tu histórico real.</span>
            </li>
            <li>
              <CheckIcon />
              <span>Facturas y RCV validados antes de aprobar.</span>
            </li>
            <li>
              <CheckIcon />
              <span>Ahorro documentado para decidir con números.</span>
            </li>
          </ul>

          <button type="button" className="button primary landing-cta" onClick={onStart}>
            Quiero saber cuánto pierdo
            <ArrowRightIcon />
          </button>
          <p className="landing-result-disclaimer">
            Estimación referencial, no una promesa de resultado. El ahorro real depende de tu
            operación y del nivel de sobrecosto que exista hoy.
          </p>
        </div>
      </div>
    </section>
  );
}

export default function LandingPage({ onLogin, onRegister }) {
  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-container landing-nav-inner">
          <a className="landing-logo" href="#top" aria-label="NEXORA, inicio">
            <span className="brand-mark">N</span>
            <span className="landing-logo-name">NEXORA</span>
          </a>

          <nav className="landing-nav-links" aria-label="Secciones">
            <a href="#problema">El problema</a>
            <a href="#como-funciona">Cómo funciona</a>
            <a href="#ahorro">Ahorro</a>
            <a href="#precios">Precios</a>
            <a href="#preguntas">Preguntas</a>
          </nav>

          <div className="landing-nav-cta">
            <button type="button" className="button ghost" onClick={onLogin}>
              Ingresar
            </button>
            <button type="button" className="button primary" onClick={onRegister}>
              Probar gratis
            </button>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="landing-hero">
          <div className="landing-container landing-hero-grid">
            <div className="landing-hero-copy">
              <span className="landing-eyebrow">
                Auditoría de compras para pymes, ferreterías y distribuidoras
              </span>
              <h1 className="landing-h1">
                Cada factura que apruebas sin auditar es <em>margen que se te escapa</em>.
              </h1>
              <p className="landing-sub">
                NEXORA revisa tus facturas, cotizaciones y el RCV del SII, detecta sobrecostos y
                errores, y te muestra exactamente dónde estás pagando de más. En minutos, no en
                semanas.
              </p>

              <div className="landing-cta-row">
                <button type="button" className="button primary landing-cta" onClick={onRegister}>
                  Auditar mis compras gratis
                  <ArrowRightIcon />
                </button>
                <a className="button ghost landing-cta" href="#como-funciona">
                  Ver cómo funciona
                </a>
              </div>

              <ul className="landing-microtrust">
                <li>
                  <CheckIcon /> Sin tarjeta de crédito
                </li>
                <li>
                  <CheckIcon /> Configúralo en minutos
                </li>
                <li>
                  <CheckIcon /> Datos aislados por empresa
                </li>
              </ul>
            </div>

            <HeroPanel />
          </div>

          <div className="landing-container landing-trust">
            <span className="landing-trust-label">Funciona con lo que ya usas</span>
            <ul className="landing-trust-list">
              {INTEGRATIONS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="landing-section" id="problema">
          <div className="landing-container">
            <div className="landing-section-head">
              <span className="landing-pill">El costo invisible</span>
              <h2 className="landing-h2">Lo que no auditas, lo pagas igual.</h2>
              <p className="landing-section-sub">
                En una pyme que compra $50 millones al mes, un sobrecosto silencioso del 3% son
                <b> $18 millones al año</b> que salen de tu bolsillo sin que nadie lo note.
              </p>
            </div>

            <div className="landing-compare">
              <div className="landing-compare-col is-before">
                <header>
                  <span className="landing-compare-badge">Antes de NEXORA</span>
                  <h3>Comprar a ciegas</h3>
                </header>
                <ul className="landing-compare-list">
                  {PAIN_POINTS.map((item) => (
                    <li key={item.title}>
                      <span className="landing-compare-icon">
                        <item.icon />
                      </span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.text}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="landing-compare-col is-after">
                <header>
                  <span className="landing-compare-badge">Con NEXORA</span>
                  <h3>Comprar con control</h3>
                </header>
                <ul className="landing-compare-list">
                  {OUTCOMES.map((item) => (
                    <li key={item.title}>
                      <span className="landing-compare-icon">
                        <item.icon />
                      </span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.text}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-section" id="funciones">
          <div className="landing-container">
            <div className="landing-section-head">
              <span className="landing-pill">Qué hace por tu negocio</span>
              <h2 className="landing-h2">Menos planillas. Más control y ahorro.</h2>
              <p className="landing-section-sub">
                NEXORA convierte documentos dispersos en decisiones accionables, sin cambiar tu
                forma de comprar.
              </p>
            </div>

            <div className="landing-features">
              {FEATURES.map((item) => (
                <article key={item.title} className="landing-feature">
                  <span className="landing-feature-icon">
                    <item.icon />
                  </span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="landing-section" id="como-funciona">
          <div className="landing-container">
            <div className="landing-section-head">
              <span className="landing-pill">Cómo funciona</span>
              <h2 className="landing-h2">De la pila de documentos al ahorro, en 3 pasos.</h2>
            </div>

            <ol className="landing-steps">
              {STEPS.map((step, index) => (
                <li key={step.title} className="landing-step">
                  <span className="landing-step-number">{index + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>

            <div className="landing-steps-cta">
              <button type="button" className="button primary landing-cta" onClick={onRegister}>
                Empezar gratis
                <ArrowRightIcon />
              </button>
              <span className="landing-steps-note">
                <HistoryIcon /> Tus primeros hallazgos en minutos
              </span>
            </div>
          </div>
        </section>

        <SavingsCalculator onStart={onRegister} />

        <section className="landing-section landing-pricing-section" id="precios">
          <div className="landing-container">
            <PricingTable
              actionLabel="Empezar gratis con"
              title="Precios claros, sin sorpresas"
              subtitle="Empieza gratis y escala cuando tu operación lo necesite. Sin permanencia."
              onSelect={onRegister}
            />
          </div>
        </section>

        <section className="landing-section" id="preguntas">
          <div className="landing-container landing-faq">
            <div className="landing-section-head">
              <span className="landing-pill">Preguntas frecuentes</span>
              <h2 className="landing-h2">Lo que suelen preguntar antes de empezar.</h2>
            </div>

            <div className="landing-faq-list">
              {FAQS.map((item) => (
                <details key={item.q} className="landing-faq-item">
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="landing-section">
          <div className="landing-container">
            <div className="landing-final">
              <div className="landing-final-copy">
                <span className="landing-pill">Es ahora o nunca</span>
                <h2 className="landing-h2">Cada mes sin auditar es margen que regalas.</h2>
                <p>
                  Empieza gratis y descubre en minutos cuánto estás pagando de más en tus compras.
                </p>
              </div>
              <div className="landing-final-actions">
                <button type="button" className="button primary landing-cta" onClick={onRegister}>
                  Crear mi cuenta gratis
                  <ArrowRightIcon />
                </button>
                <button type="button" className="button ghost landing-cta" onClick={onLogin}>
                  Ya tengo cuenta
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-grid">
          <div className="landing-footer-brand">
            <a className="landing-logo" href="#top" aria-label="NEXORA, inicio">
              <span className="brand-mark">N</span>
              <span className="landing-logo-name">NEXORA</span>
            </a>
            <p>Auditoría de compras y precios para pymes que quieren dejar de pagar de más.</p>
          </div>

          <div className="landing-footer-col">
            <span>Producto</span>
            <a href="#funciones">Funciones</a>
            <a href="#como-funciona">Cómo funciona</a>
            <a href="#precios">Precios</a>
          </div>

          <div className="landing-footer-col">
            <span>Legal</span>
            <a href="/terms.html" target="_blank" rel="noopener">
              Términos
            </a>
            <a href="/privacy.html" target="_blank" rel="noopener">
              Privacidad
            </a>
            <a href="/cookies.html" target="_blank" rel="noopener">
              Cookies
            </a>
          </div>

          <div className="landing-footer-col">
            <span>Acceso</span>
            <button type="button" onClick={onLogin}>
              Ingresar
            </button>
            <button type="button" onClick={onRegister}>
              Crear cuenta
            </button>
          </div>
        </div>

        <div className="landing-container landing-footer-bottom">
          <span>© {new Date().getFullYear()} NEXORA. Todos los derechos reservados.</span>
          <span>Hecho para pymes, ferreterías y distribuidoras de Chile.</span>
        </div>
      </footer>
    </div>
  );
}
