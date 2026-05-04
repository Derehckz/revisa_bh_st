import { type ReactNode, lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/app/layouts/app-shell";
import { Skeleton } from "@/shared/ui/skeleton";

const DashboardPage = lazy(() => import("@/features/dashboard/page").then((m) => ({ default: m.DashboardPage })));
const PeriodPage = lazy(() => import("@/features/period/page").then((m) => ({ default: m.PeriodPage })));
const BoletasPage = lazy(() => import("@/features/boletas/page").then((m) => ({ default: m.BoletasPage })));
const DocentesPage = lazy(() => import("@/features/docentes/page").then((m) => ({ default: m.DocentesPage })));
const OperacionPage = lazy(() => import("@/features/operacion/page").then((m) => ({ default: m.OperacionPage })));
const RunsPage = lazy(() => import("@/features/runs/page").then((m) => ({ default: m.RunsPage })));
const SettingsPage = lazy(() => import("@/features/settings/page").then((m) => ({ default: m.SettingsPage })));

function withSuspense(node: ReactNode) {
  return (
    <Suspense fallback={<div className="space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-72 w-full" /></div>}>
      {node}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: withSuspense(<DashboardPage />) },
      { path: "periodo", element: withSuspense(<PeriodPage />) },
      { path: "boletas", element: withSuspense(<BoletasPage />) },
      { path: "docentes", element: withSuspense(<DocentesPage />) },
      { path: "operacion", element: withSuspense(<OperacionPage />) },
      { path: "runs", element: withSuspense(<RunsPage />) },
      { path: "settings", element: withSuspense(<SettingsPage />) },
    ],
  },
]);
