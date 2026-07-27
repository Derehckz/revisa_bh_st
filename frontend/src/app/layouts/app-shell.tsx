import { motion } from "framer-motion";
import {
  BarChart3,
  CalendarRange,
  ClipboardList,
  Cog,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptText,
  Settings2,
  Users,
} from "lucide-react";
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
  { to: "/avance", icon: ClipboardList, label: "Avance" },
  { to: "/runs", icon: BarChart3, label: "Runs" },
  { to: "/settings", icon: Settings2, label: "Ajustes" },
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const width = useMemo(() => (collapsed ? 72 : 232), [collapsed]);

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
        transition={{ type: "spring", stiffness: 320, damping: 32 }}
        className="sticky top-0 z-20 flex h-screen flex-col border-r border-border/80 bg-muted/40 backdrop-blur-xl"
      >
        <div className={cn("flex h-14 items-center gap-2 px-3", collapsed ? "justify-center" : "justify-between")}>
          {!collapsed && (
            <div className="min-w-0 pl-1">
              <p className="truncate text-[0.8125rem] font-semibold tracking-tight text-foreground">
                Boletas Honorarios
              </p>
              <p className="truncate text-2xs text-muted-foreground">Operación mensual</p>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 shrink-0 px-0"
            onClick={() => setCollapsed((v) => !v)}
            aria-label="Alternar barra lateral (Ctrl+B)"
            title="Ctrl+B"
          >
            {collapsed ? <PanelLeftOpen size={16} strokeWidth={1.75} /> : <PanelLeftClose size={16} strokeWidth={1.75} />}
          </Button>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-3">
          {navItems.map((item) => {
            const active =
              item.to === "/"
                ? location.pathname === "/"
                : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[0.8125rem] font-medium tracking-tight transition-colors duration-150",
                  collapsed && "justify-center px-0",
                  active
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:bg-card/70 hover:text-foreground"
                )}
              >
                <Icon
                  size={17}
                  strokeWidth={active ? 2 : 1.75}
                  className={cn(active ? "text-primary" : "text-muted-foreground group-hover:text-foreground")}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </motion.aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <Topbar />
        <main
          id="main-content"
          className={cn(
            "mx-auto w-full flex-1",
            location.pathname.startsWith("/avance")
              ? "max-w-[1800px] px-3 py-3 md:px-4 md:py-4"
              : "max-w-[1400px] px-4 py-5 md:px-6 md:py-6 lg:px-8"
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
