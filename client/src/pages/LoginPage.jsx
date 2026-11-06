import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { CheckIcon, CloseIcon, MailIcon, LockIcon, ArrowLeftIcon } from "../components/Icons";
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

const MODES = {
  LOGIN: "login",
  REGISTER: "register",
  FORGOT: "forgot",
  RESET: "reset",
  VERIFY: "verify",
};

export default function LoginPage({ error }) {
  const { login, register, loginWithGoogle, forgotPassword, resetPassword, verifyEmail, resendVerification } = useAuth();
  const [mode, setMode] = useState(MODES.LOGIN);
  const [form, setForm] = useState({ name: "", email: "", password: "", token: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth") === "error";
  const authMessage = authError
    ? "No pudimos completar el inicio de sesión con Google. Intenta nuevamente."
    : "";
  const verifyToken = params.get("verify_token");
  const resetToken = params.get("reset_token");
  const feedback = message || authMessage || error;

  // Auto-switch mode based on URL tokens
  const checks = useMemo(() => passwordChecks(form.password), [form.password]);
  const strength = checks.filter(Boolean).length;

  useEffect(() => {
    if (verifyToken && mode === MODES.LOGIN) {
      setMode(MODES.VERIFY);
      setForm((prev) => ({ ...prev, token: verifyToken }));
    } else if (resetToken && mode === MODES.LOGIN) {
      setMode(MODES.RESET);
      setForm((prev) => ({ ...prev, token: resetToken }));
    }
  }, [verifyToken, resetToken, mode]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function switchMode(next) {
    setMode(next);
    setMessage("");
    setSuccess("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    setSuccess("");

    if ((mode === MODES.LOGIN || mode === MODES.REGISTER) && !acceptedTerms) {
      setMessage("Debes aceptar los Términos y Condiciones y la Política de Privacidad para continuar.");
      return;
    }

    const email = form.email.trim().toLowerCase();
    if (!EMAIL_RE.test(email) && (mode === MODES.LOGIN || mode === MODES.REGISTER || mode === MODES.FORGOT)) {
      setMessage("Ingresa un email válido.");
      return;
    }
    if (mode === MODES.REGISTER) {
      if (form.name.trim().length < 2) {
        setMessage("Ingresa tu nombre completo.");
        return;
      }
      if (strength < checks.length) {
        setMessage("La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un número.");
        return;
      }
    } else if (mode === MODES.RESET) {
      if (!form.token) {
        setMessage("Falta el token de recuperación.");
        return;
      }
      if (strength < checks.length) {
        setMessage("La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un número.");
        return;
      }
    } else if (mode === MODES.LOGIN && !form.password) {
      setMessage("Ingresa tu contraseña.");
      return;
    } else if (mode === MODES.VERIFY && !form.token) {
      setMessage("Falta el token de verificación.");
      return;
    }

    setPending(true);
    try {
      if (mode === MODES.LOGIN) {
        const recaptchaToken = await getRecaptchaToken("login");
        await login({ email, password: form.password, recaptchaToken });
      } else if (mode === MODES.REGISTER) {
        const recaptchaToken = await getRecaptchaToken("register");
        await register({
          name: form.name.trim(),
          email,
          password: form.password,
          recaptchaToken,
        });
      } else if (mode === MODES.FORGOT) {
        const recaptchaToken = await getRecaptchaToken("forgot_password");
        await forgotPassword({ email, recaptchaToken });
        setSuccess("Si el email existe, recibirás un enlace de recuperación.");
      } else if (mode === MODES.RESET) {
        await resetPassword({ token: form.token, password: form.password });
        setSuccess("Contraseña actualizada. Ya puedes iniciar sesión.");
        setTimeout(() => switchMode(MODES.LOGIN), 2000);
      } else if (mode === MODES.VERIFY) {
        await verifyEmail({ token: form.token });
        setSuccess("Email verificado correctamente.");
        setTimeout(() => switchMode(MODES.LOGIN), 2000);
      }
    } catch (err) {
      setMessage(err.message || "No pudimos completar la operación.");
    } finally {
      setPending(false);
    }
  }

  async function handleResendVerification() {
    setMessage("");
    setSuccess("");
    if (!EMAIL_RE.test(form.email)) {
      setMessage("Ingresa un email válido.");
      return;
    }
    setPending(true);
    try {
      await resendVerification({ email: form.email });
      setSuccess("Si la cuenta existe y no está verificada, recibirás un correo.");
    } catch (err) {
      setMessage(err.message || "No se pudo reenviar el correo.");
    } finally {
      setPending(false);
    }
  }

  function handleGoogleLogin() {
    if (!acceptedTerms) {
      setMessage("Debes aceptar los Términos y Condiciones y la Política de Privacidad para continuar.");
      return;
    }
    setMessage("");
    loginWithGoogle();
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
              aria-selected={mode === MODES.LOGIN}
              className={`auth-tab ${mode === MODES.LOGIN ? "active" : ""}`}
              onClick={() => switchMode(MODES.LOGIN)}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === MODES.REGISTER}
              className={`auth-tab ${mode === MODES.REGISTER ? "active" : ""}`}
              onClick={() => switchMode(MODES.REGISTER)}
            >
              Crear cuenta
            </button>
          </div>

          <div className="login-card-head">
            <h2>
              {mode === MODES.LOGIN && "Accede a tu panel"}
              {mode === MODES.REGISTER && "Crea tu espacio de trabajo"}
              {mode === MODES.FORGOT && "Recuperar contraseña"}
              {mode === MODES.RESET && "Nueva contraseña"}
              {mode === MODES.VERIFY && "Verificar email"}
            </h2>
            <p>
              {mode === MODES.LOGIN && "Ingresa con tu email o usa tu cuenta corporativa de Google."}
              {mode === MODES.REGISTER && "Registra tu organización en menos de un minuto."}
              {mode === MODES.FORGOT && "Te enviaremos un enlace para restablecer tu contraseña."}
              {mode === MODES.RESET && "Tu nueva contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número."}
              {mode === MODES.VERIFY && "Ingresa el token recibido por email para verificar tu cuenta."}
            </p>
          </div>

          {feedback ? (
            <div className="alert error" role="alert">
              {feedback}
            </div>
          ) : null}
          {success ? (
            <div className="alert success" role="alert">
              {success}
            </div>
          ) : null}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {mode === MODES.REGISTER ? (
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

            {mode !== MODES.VERIFY && mode !== MODES.RESET ? (
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
            ) : null}

            {mode === MODES.LOGIN || mode === MODES.REGISTER || mode === MODES.RESET ? (
              <label className="auth-field">
                <span>Contraseña</span>
                <div className="auth-password">
                  <input
                    type={showPassword ? "text" : "password"}
                    aria-label="Contraseña"
                    autoComplete={mode === MODES.LOGIN ? "current-password" : "new-password"}
                    placeholder={mode === MODES.LOGIN ? "Tu contraseña" : "Mínimo 8 caracteres"}
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
            ) : null}

            {mode === MODES.REGISTER ? (
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

            {mode === MODES.RESET || mode === MODES.VERIFY ? (
              <label className="auth-field">
                <span>Token</span>
                <input
                  type="text"
                  aria-label="Token de verificación o recuperación"
                  autoComplete="one-time-code"
                  placeholder="Pega aquí el token recibido por email"
                  value={form.token}
                  onChange={(event) => update("token", event.target.value)}
                  disabled={pending}
                  required
                />
              </label>
            ) : null}

            {mode === MODES.LOGIN || mode === MODES.REGISTER ? (
              <label className="auth-consent">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(event) => setAcceptedTerms(event.target.checked)}
                  disabled={pending}
                  required
                />
                <span>
                  Acepto los{" "}
                  <a
                    href="/terms.html"
                    target="_blank"
                    rel="noopener"
                    onClick={(event) => event.stopPropagation()}
                  >
                    Términos y Condiciones
                  </a>{" "}
                  y la{" "}
                  <a
                    href="/privacy.html"
                    target="_blank"
                    rel="noopener"
                    onClick={(event) => event.stopPropagation()}
                  >
                    Política de Privacidad
                  </a>{" "}
                  de Nexora.
                </span>
              </label>
            ) : null}

            <button type="submit" className="button primary full auth-submit" disabled={pending}>
              {pending
                ? mode === MODES.LOGIN
                  ? "Ingresando…"
                  : mode === MODES.REGISTER
                  ? "Creando cuenta…"
                  : mode === MODES.FORGOT
                  ? "Enviando…"
                  : mode === MODES.RESET
                  ? "Actualizando…"
                  : "Verificando…"
                : mode === MODES.LOGIN
                ? "Ingresar con email"
                : mode === MODES.REGISTER
                ? "Crear cuenta gratis"
                : mode === MODES.FORGOT
                ? "Enviar enlace de recuperación"
                : mode === MODES.RESET
                ? "Actualizar contraseña"
                : "Verificar email"}
            </button>
          </form>

          {mode === MODES.FORGOT && (
            <div className="login-divider">
              <span />
              <small>¿No recibiste el email?</small>
              <span />
            </div>
          )}
          {mode === MODES.FORGOT && (
            <button type="button" className="button secondary full" onClick={handleResendVerification} disabled={pending}>
              Reenviar correo de verificación
            </button>
          )}

          {mode !== MODES.FORGOT && mode !== MODES.RESET && mode !== MODES.VERIFY && (
            <>
              <div className="login-divider">
                <span />
                <small>o continúa con</small>
                <span />
              </div>

              <button type="button" className="google-button" onClick={handleGoogleLogin} disabled={pending}>
                <GoogleMark />
                Continuar con Google
              </button>

              <p className="login-note">
                Al ingresar aceptas que los documentos que subas sean procesados para extraer ítems,
                precios y unidades. Los datos quedan aislados por organización.
              </p>
            </>
          )}

          <div className="auth-links">
            {mode === MODES.LOGIN && (
              <>
                <button type="button" className="link-button" onClick={() => switchMode(MODES.FORGOT)}>
                  ¿Olvidaste tu contraseña?
                </button>
                <button type="button" className="link-button" onClick={() => switchMode(MODES.REGISTER)}>
                  ¿No tienes cuenta? Crear una
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={handleResendVerification}
                  disabled={pending}
                >
                  Reenviar email de verificación
                </button>
              </>
            )}
            {mode === MODES.REGISTER && (
              <button type="button" className="link-button" onClick={() => switchMode(MODES.LOGIN)}>
                ¿Ya tienes cuenta? Iniciar sesión
              </button>
            )}
            {(mode === MODES.FORGOT || mode === MODES.RESET || mode === MODES.VERIFY) && (
              <button type="button" className="link-button" onClick={() => switchMode(MODES.LOGIN)}>
                <ArrowLeftIcon /> Volver al inicio de sesión
              </button>
            )}
          </div>

          <p className="login-footnote">
            ¿Necesitas acceso para tu equipo? Los roles se administran desde el panel de equipo por el
            owner de la organización.
          </p>
        </div>

        <p className="login-footnote legal-links">
          <a href="/terms.html" target="_blank" rel="noopener">Términos de servicio</a>
          <span>·</span>
          <a href="/privacy.html" target="_blank" rel="noopener">Política de privacidad</a>
          <span>·</span>
          <a href="/cookies.html" target="_blank" rel="noopener">Cookies</a>
        </p>
      </section>

      <section className="login-pricing">
        <PricingTable
          actionLabel="Crear cuenta con"
          title="Empieza gratis y escala cuando lo necesites"
          subtitle="Todos los planes incluyen auditoría de precios, histórico y exportaciones."
          onSelect={() => {
            switchMode(MODES.REGISTER);
            document.getElementById("auth-name")?.focus();
          }}
        />
      </section>
    </div>
  );
}
