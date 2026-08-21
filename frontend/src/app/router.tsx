import { type ReactNode, lazy, Suspense } from "react";
import { createBrowserRouter, isRouteErrorResponse, useRouteError } from "react-router-dom";
import { AppShell } from "@/app/layouts/app-shell";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

const CHUNK_RELOAD_KEY = "bh_chunk_reload";

/** Tras un rebuild, el navegador puede pedir un .js con hash viejo. Recarga una vez. */
function lazyPage(loader: () => Promise<{ default: React.ComponentType }>) {
  return lazy(() =>
    loader().catch((err: unknown) => {
      const msg = String(err);
      const isChunk =
        msg.includes("Failed to fetch dynamically imported module") ||
        msg.includes("Importing a module script failed") ||
        msg.includes("error loading dynamically imported module");
      if (isChunk && !sessionStorage.getItem(CHUNK_RELOAD_KEY)) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, "1");
        window.location.reload();
        return new Promise(() => {});
      }
      sessionStorage.removeItem(CHUNK_RELOAD_KEY);
      throw err;
    })
  );
}

const DashboardPage = lazyPage(() =>
  import("@/features/dashboard/page").then((m) => ({ default: m.DashboardPage }))
);
const PeriodPage = lazyPage(() =>
  import("@/features/period/page").then((m) => ({ default: m.PeriodPage }))
);
const BoletasPage = lazyPage(() =>
  import("@/features/boletas/page").then((m) => ({ default: m.BoletasPage }))
);
const DocentesPage = lazyPage(() =>
  import("@/features/docentes/page").then((m) => ({ default: m.DocentesPage }))
);
const OperacionPage = lazyPage(() =>
  import("@/features/operacion/page").then((m) => ({ default: m.OperacionPage }))
);
const InformePage = lazyPage(() =>
  import("@/features/informe/page").then((m) => ({ default: m.InformePage }))
);
const RunsPage = lazyPage(() =>
  import("@/features/runs/page").then((m) => ({ default: m.RunsPage }))
);
const SettingsPage = lazyPage(() =>
  import("@/features/settings/page").then((m) => ({ default: m.SettingsPage }))
);
const AvancePage = lazyPage(() =>
  import("@/features/avance/page").then((m) => ({ default: m.AvancePage }))
);

function withSuspense(node: ReactNode) {
  return (
    <Suspense
      fallback={
        <div className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-72 w-full" />
        </div>
      }
    >
      {node}
    </Suspense>
  );
}

function RouteError() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : "Error inesperado";

  const isChunk =
    message.includes("Failed to fetch dynamically imported module") ||
    message.includes("Importing a module script failed");

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 px-6 py-16">
      <h1 className="text-xl font-semibold tracking-tight">
        {isChunk ? "La interfaz se actualizó" : "Algo salió mal"}
      </h1>
      <p className="text-sm text-muted-foreground">
        {isChunk
          ? "Se recargó el código del servidor. Pulsa recargar para continuar."
          : message}
      </p>
      <Button
        onClick={() => {
          sessionStorage.removeItem(CHUNK_RELOAD_KEY);
          window.location.assign(window.location.pathname);
        }}
      >
        Recargar
      </Button>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: withSuspense(<DashboardPage />) },
      { path: "periodo", element: withSuspense(<PeriodPage />) },
      { path: "boletas", element: withSuspense(<BoletasPage />) },
      { path: "docentes", element: withSuspense(<DocentesPage />) },
      { path: "operacion", element: withSuspense(<OperacionPage />), errorElement: <RouteError /> },
      { path: "avance", element: withSuspense(<AvancePage />), errorElement: <RouteError /> },
      { path: "informe", element: withSuspense(<InformePage />), errorElement: <RouteError /> },
      { path: "runs", element: withSuspense(<RunsPage />) },
      { path: "settings", element: withSuspense(<SettingsPage />) },
    ],
  },
]);
