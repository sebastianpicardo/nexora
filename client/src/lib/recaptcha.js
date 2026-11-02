import { api } from "./api";

const BUILD_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || "";

let siteKeyPromise = null;
let loaderPromise = null;

async function resolveSiteKey() {
  if (BUILD_SITE_KEY) return BUILD_SITE_KEY;
  if (!siteKeyPromise) {
    siteKeyPromise = api("/api/auth/config")
      .then((data) => data?.recaptcha_site_key || "")
      .catch(() => "");
  }
  return siteKeyPromise;
}

function loadScript(siteKey) {
  if (window.grecaptcha?.execute) return Promise.resolve(true);
  if (loaderPromise) return loaderPromise;

  loaderPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-nexora-recaptcha]");
    if (existing) {
      existing.addEventListener("load", () => resolve(true));
      existing.addEventListener("error", () => reject(new Error("No se pudo cargar reCAPTCHA.")));
      return;
    }

    const script = document.createElement("script");
    script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(siteKey)}`;
    script.async = true;
    script.defer = true;
    script.dataset.nexoraRecaptcha = "true";
    script.onload = () => resolve(true);
    script.onerror = () => {
      loaderPromise = null;
      reject(new Error("No se pudo cargar reCAPTCHA."));
    };
    document.head.appendChild(script);
  });

  return loaderPromise;
}

export async function getRecaptchaToken(action) {
  try {
    const siteKey = await resolveSiteKey();
    if (!siteKey) return null;
    await loadScript(siteKey);
    await new Promise((resolve) => window.grecaptcha.ready(resolve));
    return await window.grecaptcha.execute(siteKey, { action });
  } catch {
    return null;
  }
}
