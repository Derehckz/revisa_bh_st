import { useRef } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  AlertCircle,
  Circle,
  FolderOpen,
  Loader2,
  Upload,
  ArrowRight,
} from "lucide-react";
import type { PeriodSetupItem, PeriodSetupResponse } from "@/shared/api/types";
import { usePeriodUpload } from "@/shared/api/queries";
import { apiPost, mapApiErrorMessage, type ApiError } from "@/shared/api/client";
import { useAppConfig } from "@/app/app-config";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useToast } from "@/shared/ui/toast";

type Props = {
  setup: PeriodSetupResponse;
  onGoToStep0: () => void;
};

function ItemIcon({ ok, blocking }: { ok: boolean; blocking: boolean }) {
  if (ok) return <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-green-700" />;
  if (blocking) return <AlertCircle size={16} className="mt-0.5 shrink-0 text-amber-800" />;
  return <Circle size={16} className="mt-0.5 shrink-0 text-muted-foreground" />;
}

function UploadButton({
  kind,
  label,
  accept,
  year,
  month,
  disabled,
}: {
  kind: "maestro" | "bd" | "adjunto";
  label: string;
  accept: string;
  year: number;
  month: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { baseUrl, apiKey } = useAppConfig();
  const upload = usePeriodUpload(baseUrl, apiKey);
  const { push } = useToast();

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          upload.mutate(
            { year, month, kind, file },
            {
              onSuccess: (res) => push(res.message || "Archivo subido", "success"),
              onError: (err) =>
                push(
                  mapApiErrorMessage(err as unknown as ApiError) || "No se pudo subir",
                  "error"
                ),
            }
          );
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || upload.isPending}
        onClick={() => inputRef.current?.click()}
      >
        {upload.isPending ? (
          <Loader2 size={14} className="mr-1.5 animate-spin" />
        ) : (
          <Upload size={14} className="mr-1.5" />
        )}
        {label}
      </Button>
    </>
  );
}

function SetupRow({
  item,
  year,
  month,
}: {
  item: PeriodSetupItem;
  year: number;
  month: string;
}) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-2 rounded-md border border-border/70 bg-muted/20 px-3 py-2">
      <div className="flex min-w-0 flex-1 items-start gap-2 text-sm">
        <ItemIcon ok={item.ok} blocking={item.blocking} />
        <div className="min-w-0">
          <p className={item.ok ? "text-foreground" : item.blocking ? "text-amber-950" : "text-muted-foreground"}>
            {item.label}
          </p>
          {!item.ok && item.message ? (
            <p className="text-xs text-muted-foreground">{item.message}</p>
          ) : null}
          {item.ok && item.files?.length ? (
            <p className="text-xs text-muted-foreground">{item.files.join(", ")}</p>
          ) : null}
        </div>
      </div>
      {!item.ok && item.kind === "maestro" && (
        <UploadButton kind="maestro" label="Subir maestro" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" year={year} month={month} />
      )}
      {!item.ok && item.kind === "bd" && (
        <UploadButton kind="bd" label="Subir BD" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" year={year} month={month} />
      )}
      {!item.ok && item.kind === "adjunto" && (
        <UploadButton kind="adjunto" label="Subir PDF" accept=".pdf,application/pdf" year={year} month={month} />
      )}
    </li>
  );
}

export function PeriodSetupCard({ setup, onGoToStep0 }: Props) {
  const { baseUrl, apiKey } = useAppConfig();
  const { push } = useToast();

  if (!setup.needs_setup_panel && setup.setup_complete) return null;

  async function openFolder() {
    try {
      const res = await apiPost<{ message?: string }>(baseUrl, apiKey, "/operations/local/open", {
        year: setup.year,
        month: setup.month,
        target: "folder",
      });
      push(res.message || "Abriendo carpeta…", "success");
    } catch (err) {
      push(mapApiErrorMessage(err as ApiError) || "No se pudo abrir la carpeta", "error");
    }
  }

  return (
    <Card className="border-primary/25 bg-primary/[0.03]">
      <CardHeader className="space-y-1 py-3">
        <CardTitle className="text-sm font-semibold tracking-tight">
          Preparar {setup.month} {setup.year}
        </CardTitle>
        <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">
          Antes del paso 0: carpeta del mes, Excel maestro, base de docentes y PDF de ejemplo.
          Si falta la API key, configúrala en Ajustes.
        </p>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {!apiKey && (
          <p className="rounded-md border border-amber-500/40 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            Falta la API key.{" "}
            <Link to="/settings" className="font-medium underline underline-offset-2">
              Ir a Ajustes
            </Link>
          </p>
        )}

        <ul className="space-y-2">
          {setup.items.map((item) => (
            <SetupRow key={item.id} item={item} year={setup.year} month={setup.month} />
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => void openFolder()}>
            <FolderOpen size={14} className="mr-1.5" />
            Abrir carpeta del mes
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!setup.ready_for_step0}
            onClick={onGoToStep0}
          >
            Ir al paso 0
            <ArrowRight size={14} className="ml-1.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
