import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, googleLoginUrl } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [organization, setOrganization] = useState(null);
  const [billing, setBilling] = useState(null);
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
    if (user) refreshBilling();
    else setBilling(null);
  }, [user, refreshBilling]);

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

  const role = user?.role || "";
  const value = {
    user,
    organization,
    billing,
    loading,
    error,
    isAuthenticated: Boolean(user),
    isSuperAdmin: role === "super_admin",
    canManage: ["owner", "admin", "super_admin"].includes(role),
    canOperate: ["owner", "admin", "super_admin", "analyst", "user"].includes(role),
    loginWithGoogle,
    logout,
    refresh,
    refreshBilling,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
