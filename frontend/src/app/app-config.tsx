import { createContext, useContext, useMemo, useState } from "react";

type ConfigContextValue = {
  baseUrl: string;
  apiKey: string;
  setBaseUrl: (value: string) => void;
  setApiKey: (value: string) => void;
  /** true cuando la UI se sirve desde el mismo origen que la API (modo BH embebido). */
  sameOrigin: boolean;
};

const AppConfigContext = createContext<ConfigContextValue | null>(null);

function detectDefaultBaseUrl(): string {
  const saved = localStorage.getItem("bh_base_url");
  if (saved) return saved;
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  const port = window.location.port;
  // Vite / preview: API en otro puerto
  if (port === "5173" || port === "4173") {
    return "http://127.0.0.1:8000";
  }
  // Servido por FastAPI (mismo origen)
  return window.location.origin;
}

const defaultBaseUrl = detectDefaultBaseUrl();
const defaultApiKey = localStorage.getItem("bh_api_key") || "";
const sameOriginDefault =
  typeof window !== "undefined" &&
  defaultBaseUrl.replace(/\/$/, "") === window.location.origin.replace(/\/$/, "");

export function AppConfigProvider({ children }: { children: React.ReactNode }) {
  const [baseUrl, _setBaseUrl] = useState(defaultBaseUrl);
  const [apiKey, _setApiKey] = useState(defaultApiKey);

  const setBaseUrl = (value: string) => {
    localStorage.setItem("bh_base_url", value);
    _setBaseUrl(value);
  };

  const setApiKey = (value: string) => {
    localStorage.setItem("bh_api_key", value);
    _setApiKey(value);
  };

  const sameOrigin =
    typeof window !== "undefined" &&
    baseUrl.replace(/\/$/, "") === window.location.origin.replace(/\/$/, "");

  const value = useMemo(
    () => ({ baseUrl, apiKey, setBaseUrl, setApiKey, sameOrigin: sameOrigin || sameOriginDefault }),
    [baseUrl, apiKey, sameOrigin]
  );
  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  const ctx = useContext(AppConfigContext);
  if (!ctx) throw new Error("useAppConfig debe usarse dentro de AppConfigProvider");
  return ctx;
}
