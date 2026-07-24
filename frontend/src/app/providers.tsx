import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ToastProvider } from "@/shared/ui/toast";
import { AppConfigProvider } from "@/app/app-config";
import { ThemeProvider } from "@/app/theme";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            retry: 1,
            refetchOnWindowFocus: true,
            refetchOnReconnect: true,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AppConfigProvider>
          <ToastProvider>{children}</ToastProvider>
        </AppConfigProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
