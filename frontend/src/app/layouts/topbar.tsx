import { ChevronRight, Moon, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useTheme } from "@/app/theme";
import { Button } from "@/shared/ui/button";

const labels: Record<string, string> = {
  "/": "Dashboard",
  "/periodo": "Período",
  "/boletas": "Boletas",
  "/runs": "Runs",
  "/settings": "Configuración",
};

export function Topbar() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const label = labels[location.pathname] || "Dashboard";
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Inicio</span>
        <ChevronRight size={14} />
        <span className="font-medium text-foreground">{label}</span>
      </div>
      <Button variant="outline" className="gap-2" onClick={toggleTheme}>
        {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        <span className="text-xs">{theme === "dark" ? "Light" : "Dark"}</span>
      </Button>
    </header>
  );
}
