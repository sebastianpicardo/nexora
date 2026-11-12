export default function WelcomeBanner() {
  return (
    <section className="welcome-banner">
      <div>
        <span className="eyebrow">Bienvenido</span>
        <h2>Empieza a auditar tus compras</h2>
        <p className="muted">
          Sube tu primer documento para ver precios normalizados, excepciones y oportunidades de ahorro.
        </p>
      </div>
      <div className="welcome-banner-actions">
        <button type="button" className="primary-button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          Subir documento
        </button>
      </div>
    </section>
  );
}
