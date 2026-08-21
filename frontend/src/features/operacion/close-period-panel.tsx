import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiGet, apiPost, mapApiErrorMessage } from "@/shared/api/client";
import type { OperationJob, Period } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { periodDateRange } from "@/shared/lib/period-dates";
import { DateInput } from "@/shared/ui/date-input";
import { useToast } from "@/shared/ui/toast";
import { usePeriodOperationGuard } from "./period-operation-context";

type Props = {
  selectedPeriod: Period | undefined;
  disabled: boolean;
  baseUrl: string;
  apiKey: string;
  onJobUpdate: (job: OperationJob) => void;
  onFinished: () => void;
  /** Aviso del checklist (p. ej. informe aún no generado). */
  checklistWarn?: string | null;
};

const STEPS_BATCH = [2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitForJob(baseUrl: string, apiKey: string, jobId: string): Promise<OperationJob> {
  for (;;) {
    const job = await apiGet<OperationJob>(baseUrl, apiKey, `/operations/jobs/${jobId}`);
    if (job.status !== "running") return job;
    await sleep(1500);
  }
}

export function ClosePeriodPanel({
  selectedPeriod,
  disabled,
  baseUrl,
  apiKey,
  onJobUpdate,
  onFinished,
  checklistWarn,
}: Props) {
  const { push } = useToast();
  const { confirmBeforeOperation } = usePeriodOperationGuard();
  const monthDefaults = useMemo(() => {
    if (!selectedPeriod) return { inicio: "", fin: "", pago: "", minIso: "", maxIso: "" };
    const range = periodDateRange(selectedPeriod);
    return {
      inicio: range.inicio,
      fin: range.fin,
      pago: range.pago,
      minIso: range.minIso,
      maxIso: range.maxIso,
    };
  }, [selectedPeriod]);

  const [fechaInicio, setFechaInicio] = useState(monthDefaults.inicio);
  const [fechaFin, setFechaFin] = useState(monthDefaults.fin);
  const [fechaPago, setFechaPago] = useState(monthDefaults.pago);
  const [sendEmail, setSendEmail] = useState(false);
  const [skipEmail, setSkipEmail] = useState(true);
  const [step8DryRun, setStep8DryRun] = useState(false);
  useEffect(() => {
    setFechaInicio(monthDefaults.inicio);
    setFechaFin(monthDefaults.fin);
    setFechaPago(monthDefaults.pago);
  }, [monthDefaults.fin, monthDefaults.inicio, monthDefaults.pago]);

  const [confirmClose, setConfirmClose] = useState(false);
  const [running, setRunning] = useState(false);
  const [progressLabel, setProgressLabel] = useState("");

  async function runClose() {
    if (!selectedPeriod || !confirmClose) return;
    if (!(await confirmBeforeOperation())) return;
    setRunning(true);
    const steps = STEPS_BATCH.filter((n) => !(skipEmail && (n === 5 || n === 7)));

    try {
      for (const stageNum of steps) {
        setProgressLabel(`Paso ${stageNum}…`);
        const body: Record<string, unknown> = {
          year: selectedPeriod.year,
          month: selectedPeriod.month_name,
        };
        if (stageNum === 2) {
          body.fecha_inicio = fechaInicio;
          body.fecha_fin = fechaFin;
        }
        if (stageNum === 5 && sendEmail) {
          /* paso 5: --yes basta; sin send en API */
        }
        if (stageNum === 7 && sendEmail) {
          body.send = true;
          body.fecha_pago = fechaPago;
        }
        if (stageNum === 8) {
          body.no_interactive = true;
          body.mover = !step8DryRun;
          body.dry_run = step8DryRun;
          body.map_csv = `${selectedPeriod.year}/${selectedPeriod.month_name}/map_ip_cft.csv`;
        }
        if (stageNum === 9) {
          body.agrupar_archivos = true;
        }

        const job = await apiPost<OperationJob>(
          baseUrl,
          apiKey,
          `/operations/stages/${stageNum}/start`,
          body
        );
        onJobUpdate(job);
        const done = await waitForJob(baseUrl, apiKey, job.id);
        onJobUpdate(done);
        if (done.status === "failed") {
          push(`Cierre detenido: paso ${stageNum} falló (job ${done.id}).`, "error");
          return;
        }
      }
      push("Ejecución de pendientes completada (2–10).", "success");
      onFinished();
    } catch (e) {
      push(mapApiErrorMessage(e as never), "error");
    } finally {
      setRunning(false);
      setProgressLabel("");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Encadenar pasos 2–10 (no cierra el mes)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Ejecuta en cadena los pasos pendientes 2→10. <strong>Esto no cierra el período</strong>:
          el cierre formal está en el checklist mensual de la pestaña Cierre (congela informe y
          bloquea ediciones).
        </p>
        {checklistWarn ? (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-800">
            {checklistWarn}
          </p>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">Fecha inicio (paso 2)</span>
            <DateInput
              value={fechaInicio}
              onChange={setFechaInicio}
              disabled={running}
              minIso={monthDefaults.minIso}
              maxIso={monthDefaults.maxIso}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">Fecha fin (paso 2)</span>
            <DateInput
              value={fechaFin}
              onChange={setFechaFin}
              disabled={running}
              minIso={monthDefaults.minIso}
              maxIso={monthDefaults.maxIso}
            />
          </label>
          <label className="space-y-1 sm:col-span-2">
            <span className="text-xs text-muted-foreground">Fecha pago (paso 7, si envía correos)</span>
            <DateInput
              value={fechaPago}
              onChange={setFechaPago}
              disabled={running}
              minIso={monthDefaults.minIso}
              maxIso={monthDefaults.maxIso}
            />
          </label>
        </div>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={skipEmail} onChange={(e) => setSkipEmail(e.target.checked)} disabled={running} />
          Omitir pasos 5 y 7 (correos)
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={sendEmail}
            onChange={(e) => setSendEmail(e.target.checked)}
            disabled={running || skipEmail}
          />
          Enviar correos reales en 5 y 7
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={step8DryRun} onChange={(e) => setStep8DryRun(e.target.checked)} disabled={running} />
          Paso 8: solo simular (no crea carpetas IP/CFT)
        </label>
        <label className="flex items-center gap-2 font-medium text-red-800">
          <input type="checkbox" checked={confirmClose} onChange={(e) => setConfirmClose(e.target.checked)} disabled={running} />
          Confirmo encadenar pasos 2→10 en {selectedPeriod?.month_name} {selectedPeriod?.year} (sin cerrar el mes)
        </label>
        <Button disabled={disabled || running || !confirmClose || !selectedPeriod} onClick={() => void runClose()}>
          {running ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              {progressLabel || "Ejecutando…"}
            </span>
          ) : (
            "Encadenar pasos 2→10"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
