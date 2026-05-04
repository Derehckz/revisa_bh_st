import { motion } from "framer-motion";
import { BarChart3, CalendarRange, Cog, LayoutDashboard, ReceiptText, Settings2, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Topbar } from "@/app/layouts/topbar";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/periodo", icon: CalendarRange, label: "Período" },
  { to: "/boletas", icon: ReceiptText, label: "Boletas" },
  { to: "/docentes", icon: Users, label: "Docentes" },
  { to: "/operacion", icon: Cog, label: "Operación" },
  { to: "/runs", icon: BarChart3, label: "Runs" },
  { to: "/settings", icon: Settings2, label: "Configuración" },
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const width = useMemo(() => (collapsed ? 84 : 240), [collapsed]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        setCollapsed((v) => !v);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex min-h-screen bg-background">
      <a href="#main-content" className="skip-link">
        Saltar al contenido
      </a>
      <motion.aside
        animate={{ width }}
        transition={{ type: "spring", stiffness: 260, damping: 28 }}
        className="sticky top-0 flex h-screen flex-col border-r border-border bg-card"
      >
        <div className="flex h-14 items-center justify-between border-b border-border px-3">
          {!collapsed && <span className="text-sm font-semibold">Boletas SaaS</span>}
          <Button
            variant="ghost"
            className="text-xs"
            onClick={() => setCollapsed((v) => !v)}
            aria-label="Alternar sidebar (Ctrl+B)"
            title="Alternar sidebar (Ctrl+B)"
          >
            {collapsed ? ">>" : "<<"}
          </Button>
        </div>
        <nav className="space-y-1 p-2">
          {navItems.map((item) => {
            const active = location.pathname === item.to;
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex h-10 items-center gap-2 rounded-md px-3 text-sm transition-colors",
                  active ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                )}
              >
                <Icon size={16} />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </motion.aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar />
        <main id="main-content" className="p-4 md:p-6 lg:p-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
