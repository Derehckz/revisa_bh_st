import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

type ActiveSessionCardProps = {
  sessionId: string;
  busy?: boolean;
  hint?: string;
  onResume: () => void;
  onCancel: () => void;
};

/** Recuperación cuando hay una sesión a medias (409 / WS caído). */
export function ActiveSessionCard({
  sessionId,
  busy,
  hint,
  onResume,
  onCancel,
}: ActiveSessionCardProps) {
  return (
    <Card className="border-warning/30 bg-warning/10">
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.9375rem]">Hay un paso a medias</CardTitle>
        <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">
          {hint ??
            "Quedó pendiente de confirmar o se cortó la conexión. Continúa o cancela para empezar de nuevo."}
        </p>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" disabled={busy} onClick={onResume}>
          Continuar lo pendiente
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={onCancel}>
          Cancelar y empezar de nuevo
        </Button>
        <span className="sr-only">id {sessionId}</span>
      </CardContent>
    </Card>
  );
}

type SessionDoneCardProps = {
  title: string;
  detail: string;
  nextLabel?: string;
  onNext?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  openLabel?: string;
  onOpen?: () => void;
  openBusy?: boolean;
};

export function SessionDoneCard({
  title,
  detail,
  nextLabel,
  onNext,
  secondaryLabel,
  onSecondary,
  openLabel,
  onOpen,
  openBusy,
}: SessionDoneCardProps) {
  return (
    <Card className="border-success/25 bg-success/10">
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.9375rem] text-success">{title}</CardTitle>
        <p className="text-[0.8125rem] font-normal leading-snug text-muted-foreground">{detail}</p>
      </CardHeader>
      {(nextLabel && onNext) || (secondaryLabel && onSecondary) || (openLabel && onOpen) ? (
        <CardContent className="flex flex-wrap gap-2">
          {openLabel && onOpen ? (
            <Button type="button" size="sm" onClick={onOpen} disabled={openBusy}>
              {openLabel}
            </Button>
          ) : null}
          {nextLabel && onNext ? (
            <Button type="button" size="sm" variant={openLabel ? "outline" : "default"} onClick={onNext}>
              {nextLabel}
            </Button>
          ) : null}
          {secondaryLabel && onSecondary ? (
            <Button type="button" size="sm" variant="outline" onClick={onSecondary}>
              {secondaryLabel}
            </Button>
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  );
}
