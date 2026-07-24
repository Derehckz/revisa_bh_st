import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Period } from "@/shared/api/types";
import { invalidatePeriodViews } from "@/shared/api/queries";
import {
  assessPeriodForOperations,
  type PeriodOperationAssessment,
} from "@/shared/lib/period-operation-guard";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog";

type PeriodOperationContextValue = {
  period: Period | undefined;
  assessment: PeriodOperationAssessment;
  confirmBeforeOperation: () => Promise<boolean>;
  /** Refresca KPIs, estados de pasos, jobs y listados sin F5. */
  refreshPeriodData: () => void;
};

const PeriodOperationContext = createContext<PeriodOperationContextValue | null>(null);

type PendingConfirm = {
  title: string;
  message: string;
  resolve: (value: boolean) => void;
};

export function PeriodOperationProvider({
  period,
  children,
}: {
  period: Period | undefined;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const assessment = useMemo(() => assessPeriodForOperations(period), [period]);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);

  const confirmBeforeOperation = useCallback((): Promise<boolean> => {
    if (!assessment.needsConfirmation) {
      return Promise.resolve(true);
    }
    return new Promise((resolve) => {
      setPendingConfirm({
        title: "Período restringido",
        message: assessment.confirmMessage,
        resolve,
      });
    });
  }, [assessment.confirmMessage, assessment.needsConfirmation]);

  const refreshPeriodData = useCallback(() => {
    invalidatePeriodViews(queryClient);
  }, [queryClient]);

  const value = useMemo(
    () => ({ period, assessment, confirmBeforeOperation, refreshPeriodData }),
    [period, assessment, confirmBeforeOperation, refreshPeriodData]
  );

  return (
    <PeriodOperationContext.Provider value={value}>
      {children}
      <ConfirmDialog
        open={pendingConfirm !== null}
        title={pendingConfirm?.title ?? ""}
        message={pendingConfirm?.message ?? ""}
        confirmLabel="Sí, continuar"
        cancelLabel="Cancelar"
        variant="danger"
        onConfirm={() => {
          pendingConfirm?.resolve(true);
          setPendingConfirm(null);
        }}
        onCancel={() => {
          pendingConfirm?.resolve(false);
          setPendingConfirm(null);
        }}
      />
    </PeriodOperationContext.Provider>
  );
}

export function usePeriodOperationGuard(): PeriodOperationContextValue {
  const ctx = useContext(PeriodOperationContext);
  if (!ctx) {
    throw new Error("usePeriodOperationGuard debe usarse dentro de PeriodOperationProvider");
  }
  return ctx;
}
