import { useAuth } from "../context/AuthContext";
import { CheckIcon } from "../components/Icons";

function GoogleMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

const FEATURES = [
  "Normalización automática de unidades y monedas.",
  "Detección de alzas frente al histórico de cada proveedor.",
  "Bandeja de excepciones con evidencia y revisión humana.",
];

export default function LoginPage({ error }) {
  const { loginWithGoogle } = useAuth();
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth") === "error";
  const message = authError
    ? "No pudimos completar el inicio de sesión con Google. Intenta nuevamente."
    : error;

  return (
    <div className="login-page">
      <section className="login-hero">
        <div className="login-brand">
          <div className="brand-mark large">N</div>
          <span>NEXORA</span>
        </div>
        <div className="login-hero-copy">
          <p className="eyebrow">Inteligencia de compras para distribución industrial</p>
          <h1>Convierte cotizaciones dispersas en decisiones de compra auditables.</h1>
          <p className="login-lead">
            Centraliza documentos, normaliza unidades y detecta variaciones de precio antes de que
            afecten tu margen.
          </p>
          <ul className="feature-list">
            {FEATURES.map((feature) => (
              <li key={feature}>
                <span className="feature-check">
                  <CheckIcon />
                </span>
                {feature}
              </li>
            ))}
          </ul>
        </div>
        <div className="login-hero-footer">
          <span>NEXORA B2B</span>
          <span>Supabase · FastAPI · Render</span>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="login-card-head">
            <h2>Accede a tu panel</h2>
            <p>Usa tu cuenta corporativa de Google para continuar.</p>
          </div>

          {message ? <div className="alert error">{message}</div> : null}

          <button type="button" className="google-button" onClick={loginWithGoogle}>
            <GoogleMark />
            Continuar con Google
          </button>

          <div className="login-divider">
            <span />
            <small>Acceso seguro</small>
            <span />
          </div>

          <p className="login-note">
            Al ingresar aceptas que los documentos que subas sean procesados para extraer ítems,
            precios y unidades. Los datos quedan aislados por organización.
          </p>
        </div>
        <p className="login-footnote">
          ¿Necesitas acceso para tu equipo? Los roles se administran desde Supabase por el owner de
          la organización.
        </p>
      </section>
    </div>
  );
}
