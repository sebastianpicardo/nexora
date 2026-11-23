import { api } from "./api";

const BUILD_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || "";
const SCRIPT_ERROR =
  "No se pudo cargar reCAPTCHA. Revisa tu conexión y la política de seguridad (CSP) del sitio.";

let configPromise = null;
let loaderPromise = null;

async function resolveRecaptchaConfig() {
  if (!configPromise) {
    configPromise = api("/api/auth/config")
      .then((data) => ({
        enabled: Boolean(data?.recaptcha_enabled),
        siteKey: data?.recaptcha_site_key || "",
      }))
      .catch(() => {
        configPromise = null;
        return { enabled: false, siteKey: "" };
      });
  }

  const config = await configPromise;
  const siteKey = config.siteKey || BUILD_SITE_KEY;
  return { enabled: Boolean(config.enabled && siteKey), siteKey };
}

function loadScript(siteKey) {
  if (window.grecaptcha?.execute) return Promise.resolve();
  if (loaderPromise) return loaderPromise;

  loaderPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-nexora-recaptcha]");
    const script = existing || document.createElement("script");

    const onLoad = () => {
      if (window.grecaptcha?.execute) {
        resolve();
        return;
      }
      loaderPromise = null;
      reject(new Error(SCRIPT_ERROR));
    };
    const onError = () => {
      loaderPromise = null;
      script.remove();
      reject(new Error(SCRIPT_ERROR));
    };

    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });

    if (!existing) {
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(siteKey)}`;
      script.async = true;
      script.defer = true;
      script.dataset.nexoraRecaptcha = "true";
      document.head.appendChild(script);
    }
  });

  return loaderPromise;
}

export async function getRecaptchaToken(action) {
  try {
    const { enabled, siteKey } = await resolveRecaptchaConfig();
    if (!enabled || !siteKey) return null;

    await loadScript(siteKey);
    if (!window.grecaptcha?.execute) return null;

    await new Promise((resolve) => window.grecaptcha.ready(resolve));
    const token = await window.grecaptcha.execute(siteKey, { action });
    return token || null;
  } catch {
    return null;
  }
}
