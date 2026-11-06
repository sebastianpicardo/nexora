import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, googleLoginUrl } from "../lib/api";

const AuthContext = createContext(null);

const DEFAULT_BRAND = {
  brand_name: "",
  brand_primary_color: "#10b981",
  brand_accent_color: "#059669",
  logo_url: "",
  support_email: "",
  custom_domain: "",
  hide_powered_by: false,
};

function hexToRgba(hex, alpha = 0.12) {
  const value = String(hex || "").replace("#", "");
  if (value.length !== 6) return `rgba(16, 185, 129, ${alpha})`;
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function setBrandingVariables(data) {
  const branding = { ...DEFAULT_BRAND, ...(data || {}) };
  const root = document.documentElement;
  root.style.setProperty("--brand", branding.brand_primary_color);
  root.style.setProperty("--brand-dark", branding.brand_accent_color);
  root.style.setProperty("--brand-soft", hexToRgba(branding.brand_primary_color));
  document.title = branding.brand_name
    ? `${branding.brand_name} · Auditoría de compras`
    : "NEXORA · Auditoría de compras y precios";
  document.documentElement.dataset.whiteLabel = branding.brand_name ? "true" : "false";
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [organization, setOrganization] = useState(null);
  const [billing, setBilling] = useState(null);
  const [branding, setBranding] = useState(DEFAULT_BRAND);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshBilling = useCallback(async () => {
    try {
      const data = await api("/api/billing/summary");
      setBilling(data);
      return data;
    } catch {
      setBilling(null);
      return null;
    }
  }, []);

  const applyBranding = useCallback((data) => {
    setBranding({ ...DEFAULT_BRAND, ...(data || {}) });
    setBrandingVariables(data);
  }, []);

  const refreshBranding = useCallback(async () => {
    try {
      const data = await api("/api/enterprise/branding");
      applyBranding(data);
      return data;
    } catch {
      applyBranding(DEFAULT_BRAND);
      return null;
    }
  }, [applyBranding]);

  const refresh = useCallback(async () => {
    try {
      const data = await api("/api/auth/me");
      setUser(data.user);
      setOrganization(data.organization);
      setError("");
      return data.user;
    } catch (err) {
      if (err.status !== 401) {
        setError(err.message || "No se pudo verificar la sesión.");
      }
      setUser(null);
      setOrganization(null);
      setBilling(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (user) refreshBranding();
    else applyBranding(DEFAULT_BRAND);
  }, [user, refreshBranding, applyBranding]);

  useEffect(() => {
    if (user) refreshBilling();
    else setBilling(null);
  }, [user, refreshBilling]);

  const applySession = useCallback((data) => {
    setUser(data.user);
    setOrganization(data.organization);
    setError("");
    return data.user;
  }, []);

  const login = useCallback(
    async ({ email, password, recaptchaToken }) => {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, recaptcha_token: recaptchaToken }),
      });
      return applySession(data);
    },
    [applySession],
  );

  const register = useCallback(
    async ({ name, email, password, recaptchaToken }) => {
      const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ name, email, password, recaptcha_token: recaptchaToken }),
      });
      return applySession(data);
    },
    [applySession],
  );

  const loginWithGoogle = useCallback(() => {
    window.location.assign(googleLoginUrl());
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST", body: "{}" });
    } catch {
      setError("");
    } finally {
      setUser(null);
      setOrganization(null);
      setBilling(null);
    }
  }, []);

  const forgotPassword = useCallback(async ({ email, recaptchaToken }) => {
    const data = await api("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email, recaptcha_token: recaptchaToken }),
    });
    return data;
  }, []);

  const resetPassword = useCallback(async ({ token, password }) => {
    const data = await api("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
    return data;
  }, []);

  const verifyEmail = useCallback(async ({ token }) => {
    const data = await api("/api/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
    return data;
  }, []);

  const resendVerification = useCallback(async ({ email }) => {
    const data = await api("/api/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    return data;
  }, []);

  const role = user?.role || "";
  const value = {
    user,
    organization,
    billing,
    branding,
    loading,
    error,
    isAuthenticated: Boolean(user),
    isSuperAdmin: role === "super_admin",
    canManage: ["owner", "admin", "super_admin"].includes(role),
    canOperate: ["owner", "admin", "super_admin", "analyst", "user"].includes(role),
    login,
    register,
    loginWithGoogle,
    logout,
    refresh,
    refreshBilling,
    refreshBranding,
    applyBranding,
    forgotPassword,
    resetPassword,
    verifyEmail,
    resendVerification,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
