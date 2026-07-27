import { ChevronRight, Moon, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useTheme } from "@/app/theme";
import { Button } from "@/shared/ui/button";

const labels: Record<string, string> = {
  "/": "Dashboard",
  "/periodo": "Período",
  "/boletas": "Boletas",
  "/docentes": "Docentes",
  "/operacion": "Operación",
  "/avance": "Avance",
  "/runs": "Runs",
  "/settings": "Ajustes",
};

export function Topbar() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const label = labels[location.pathname] || "Dashboard";

  return (
    <header className="sticky top-0 z-10 flex h-12 items-center justify-between border-b border-border/70 bg-background/80 px-4 backdrop-blur-xl md:px-6 lg:px-8">
      <nav className="flex items-center gap-1.5 text-[0.8125rem] text-muted-foreground" aria-label="Breadcrumb">
        <span>BH</span>
        <ChevronRight size={12} strokeWidth={2} className="opacity-50" />
        <span className="font-medium tracking-tight text-foreground">{label}</span>
      </nav>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 gap-1.5 px-2.5 text-muted-foreground"
        onClick={toggleTheme}
        aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      >
        {theme === "dark" ? <Sun size={15} strokeWidth={1.75} /> : <Moon size={15} strokeWidth={1.75} />}
        <span className="text-xs">{theme === "dark" ? "Claro" : "Oscuro"}</span>
      </Button>
    </header>
  );
}
