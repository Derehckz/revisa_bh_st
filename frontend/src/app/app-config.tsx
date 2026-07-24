import { createContext, useContext, useMemo, useState } from "react";

type ConfigContextValue = {
  baseUrl: string;
  apiKey: string;
  setBaseUrl: (value: string) => void;
  setApiKey: (value: string) => void;
};

const AppConfigContext = createContext<ConfigContextValue | null>(null);

const defaultBaseUrl = localStorage.getItem("bh_base_url") || "http://127.0.0.1:8000";
// E12: nunca cachear una API key "por defecto" que funcione en silencio. Si no
// hay nada guardado en localStorage, arranca vacía y obliga a configurarla en
// Ajustes; evita que un valor de ejemplo del repo termine autenticando en prod.
const defaultApiKey = localStorage.getItem("bh_api_key") || "";

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

  const value = useMemo(() => ({ baseUrl, apiKey, setBaseUrl, setApiKey }), [baseUrl, apiKey]);
  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  const ctx = useContext(AppConfigContext);
  if (!ctx) throw new Error("useAppConfig debe usarse dentro de AppConfigProvider");
  return ctx;
}
