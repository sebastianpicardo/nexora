import { useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { CheckIcon } from "../components/Icons";
import PricingTable from "../components/PricingTable";
import { getRecaptchaToken } from "../lib/recaptcha";

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

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
const STRENGTH_LABELS = ["Muy débil", "Débil", "Aceptable", "Buena", "Excelente"];

function passwordChecks(password) {
  return [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
  ];
}

export default function LoginPage({ error }) {
  const { login, register, loginWithGoogle } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");

  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth") === "error";
  const authMessage = authError
    ? "No pudimos completar el inicio de sesión con Google. Intenta nuevamente."
    : "";
  const feedback = message || authMessage || error;

  const checks = useMemo(() => passwordChecks(form.password), [form.password]);
  const strength = checks.filter(Boolean).length;

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function switchMode(next) {
    setMode(next);
    setMessage("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");

    const email = form.email.trim().toLowerCase();
    if (!EMAIL_RE.test(email)) {
      setMessage("Ingresa un email válido.");
      return;
    }
    if (mode === "register") {
      if (form.name.trim().length < 2) {
        setMessage("Ingresa tu nombre completo.");
        return;
      }
      if (strength < checks.length) {
        setMessage("La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un número.");
        return;
      }
    } else if (!form.password) {
      setMessage("Ingresa tu contraseña.");
      return;
    }

    setPending(true);
    try {
      const recaptchaToken = await getRecaptchaToken(mode);
      if (mode === "login") {
        await login({ email, password: form.password, recaptchaToken });
      } else {
        await register({
          name: form.name.trim(),
          email,
          password: form.password,
          recaptchaToken,
        });
      }
    } catch (err) {
      setMessage(err.message || "No pudimos completar la operación.");
    } finally {
      setPending(false);
    }
  }

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
          <div className="auth-tabs" role="tablist" aria-label="Acceso">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={`auth-tab ${mode === "login" ? "active" : ""}`}
              onClick={() => switchMode("login")}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={`auth-tab ${mode === "register" ? "active" : ""}`}
              onClick={() => switchMode("register")}
            >
              Crear cuenta
            </button>
          </div>

          <div className="login-card-head">
            <h2>{mode === "login" ? "Accede a tu panel" : "Crea tu espacio de trabajo"}</h2>
            <p>
              {mode === "login"
                ? "Ingresa con tu email o usa tu cuenta corporativa de Google."
                : "Registra tu organización en menos de un minuto."}
            </p>
          </div>

          {feedback ? (
            <div className="alert error" role="alert">
              {feedback}
            </div>
          ) : null}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {mode === "register" ? (
              <label className="auth-field">
                <span>Nombre completo</span>
                <input
                  id="auth-name"
                  type="text"
                  aria-label="Nombre completo"
                  autoComplete="name"
                  placeholder="Ana Pérez"
                  value={form.name}
                  onChange={(event) => update("name", event.target.value)}
                  disabled={pending}
                  required
                />
              </label>
            ) : null}

            <label className="auth-field">
              <span>Email corporativo</span>
              <input
                type="email"
                inputMode="email"
                aria-label="Email corporativo"
                autoComplete="email"
                placeholder="tu@empresa.com"
                value={form.email}
                onChange={(event) => update("email", event.target.value)}
                disabled={pending}
                required
              />
            </label>

            <label className="auth-field">
              <span>Contraseña</span>
              <div className="auth-password">
                <input
                  type={showPassword ? "text" : "password"}
                  aria-label="Contraseña"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  placeholder={mode === "login" ? "Tu contraseña" : "Mínimo 8 caracteres"}
                  value={form.password}
                  onChange={(event) => update("password", event.target.value)}
                  disabled={pending}
                  required
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((value) => !value)}
                  tabIndex={-1}
                >
                  {showPassword ? "Ocultar" : "Mostrar"}
                </button>
              </div>
            </label>

            {mode === "register" ? (
              <div className="pw-meter" aria-live="polite">
                <div className="pw-meter-track">
                  <span className={`pw-meter-bar level-${strength}`} />
                </div>
                <div className="pw-meter-label">
                  <span>Seguridad: {STRENGTH_LABELS[strength]}</span>
                  <span className="pw-hints">
                    {checks[0] ? "8+" : "8+"} · {checks[1] ? "A-Z" : "A-Z"} ·{" "}
                    {checks[2] ? "a-z" : "a-z"} · {checks[3] ? "0-9" : "0-9"}
                  </span>
                </div>
              </div>
            ) : null}

            <button type="submit" className="button primary full auth-submit" disabled={pending}>
              {pending
                ? mode === "login"
                  ? "Ingresando…"
                  : "Creando cuenta…"
                : mode === "login"
                  ? "Ingresar con email"
                  : "Crear cuenta gratis"}
            </button>
          </form>

          <div className="login-divider">
            <span />
            <small>o continúa con</small>
            <span />
          </div>

          <button type="button" className="google-button" onClick={loginWithGoogle} disabled={pending}>
            <GoogleMark />
            Continuar con Google
          </button>

          <p className="login-note">
            Al ingresar aceptas que los documentos que subas sean procesados para extraer ítems,
            precios y unidades. Los datos quedan aislados por organización.
          </p>
        </div>

        <p className="login-footnote">
          ¿Necesitas acceso para tu equipo? Los roles se administran desde el panel de equipo por el
          owner de la organización.
        </p>
      </section>

      <section className="login-pricing">
        <PricingTable
          actionLabel="Crear cuenta con"
          title="Empieza gratis y escala cuando lo necesites"
          subtitle="Todos los planes incluyen auditoría de precios, histórico y exportaciones."
          onSelect={() => {
            switchMode("register");
            document.getElementById("auth-name")?.focus();
          }}
        />
      </section>
    </div>
  );
}
