import type { OutlookHealth } from "@/shared/api/types";

type Props = {
  health?: OutlookHealth | null;
  blockStart?: boolean;
  allowOverride?: boolean;
  override?: boolean;
  onOverrideChange?: (v: boolean) => void;
};

export function OutlookHealthBanner({
  health,
  blockStart = false,
  allowOverride = true,
  override = false,
  onOverrideChange,
}: Props) {
  if (!health) return null;
  if (health.ready) {
    return (
      <p className="rounded-md border border-success/25 bg-success/10 px-3 py-2 text-[0.8125rem] text-success">
        Outlook listo{health.process_running ? " (en ejecución)" : ""}.
      </p>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm">
      <p className="font-semibold tracking-tight text-foreground">Outlook no está listo</p>
      <p className="text-[0.8125rem] leading-snug text-muted-foreground">{health.message}</p>
      {allowOverride && onOverrideChange && (
        <label className="flex items-center gap-2 text-[0.8125rem] text-foreground">
          <input
            type="checkbox"
            className="rounded border-border"
            checked={override}
            onChange={(e) => onOverrideChange(e.target.checked)}
          />
          Continuar de todos modos (el paso intentará abrir Outlook)
        </label>
      )}
      {blockStart && !override && (
        <p className="text-[0.8125rem] text-muted-foreground">
          Abre Outlook o marca la casilla para continuar.
        </p>
      )}
    </div>
  );
}

export function outlookBlocksStart(health: OutlookHealth | null | undefined, override: boolean): boolean {
  if (!health) return false;
  if (health.ready) return false;
  return !override;
}
