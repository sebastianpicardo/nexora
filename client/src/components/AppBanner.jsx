export default function AppBanner({ onNavigate }) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <section className="app-banner" role="region" aria-label="Bienvenida">
      <div className="banner-copy">
        <span className="banner-kicker">Bienvenido a NEXORA</span>
        <h2>Convierte tus documentos de compra en decisiones claras</h2>
        <p>
          Sube cotizaciones y facturas, detecta sobreprecios, revisa excepciones y controla tu cuota en minutos.
        </p>
        <div className="banner-actions">
          <button type="button" className="banner-primary" onClick={() => onNavigate?.("documents")}>
            Subir documento
          </button>
          <button type="button" className="banner-secondary" onClick={() => onNavigate?.("dashboard")}>
            Ver resumen
          </button>
        </div>
      </div>
      <div className="banner-visual" aria-hidden="true">
        <svg viewBox="0 0 220 160" role="img">
          <defs>
            <linearGradient id="bannerPaper" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="100%" stopColor="#dbeafe" />
            </linearGradient>
            <linearGradient id="bannerChart" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>
          <rect x="28" y="18" width="118" height="124" rx="16" fill="url(#bannerPaper)" />
          <rect x="46" y="42" width="78" height="8" rx="4" fill="#94a3b8" opacity="0.55" />
          <rect x="46" y="62" width="58" height="8" rx="4" fill="#94a3b8" opacity="0.4" />
          <rect x="46" y="82" width="72" height="8" rx="4" fill="#94a3b8" opacity="0.4" />
          <rect x="46" y="102" width="48" height="8" rx="4" fill="#94a3b8" opacity="0.4" />
          <path d="M154 118 L176 92 L194 104 L212 68" fill="none" stroke="url(#bannerChart)" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="212" cy="68" r="7" fill="#34d399" />
          <circle cx="154" cy="118" r="7" fill="#10b981" />
        </svg>
      </div>
      <button
        type="button"
        className="banner-close"
        onClick={() => setVisible(false)}
        aria-label="Cerrar aviso"
      >
        ×
      </button>
    </section>
  );
}
