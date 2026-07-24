import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import type { PendingPrompt } from "./use-interactive-session";

type MailPreviewPayload = {
  mail?: { subject?: string; html_body?: string; to?: string };
  docente?: { name?: string; email?: string; monto?: string };
  cli_summary?: string;
};

type Props = {
  pendingPrompt: PendingPrompt;
  lastPreviewEvent?: { payload: Record<string, unknown> } | null;
  onAccept: () => void;
  onSkip: () => void;
  onCancel: () => void;
  acceptLabel?: string;
  skipLabel?: string;
};

export function MailReviewPrompt({
  pendingPrompt,
  lastPreviewEvent,
  onAccept,
  onSkip,
  onCancel,
  acceptLabel = "Continuar",
  skipLabel = "Omitir",
}: Props) {
  const preview = (lastPreviewEvent?.payload ?? pendingPrompt.payload) as MailPreviewPayload;
  const mail = preview.mail ?? (pendingPrompt.payload as MailPreviewPayload).mail;

  return (
    <Card className="border-warning/30 bg-warning/10">
      <CardHeader className="py-3">
        <CardTitle className="text-sm">{pendingPrompt.title || "Revisar correo"}</CardTitle>
        <p className="text-xs text-muted-foreground">{pendingPrompt.message}</p>
        {preview.cli_summary && (
          <p className="text-xs text-muted-foreground mt-1">{preview.cli_summary}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {mail && (
          <div className="rounded border bg-muted/30 p-2 max-h-56 overflow-auto text-xs">
            <p className="font-medium mb-1">{mail.subject}</p>
            <p className="text-muted-foreground mb-2">Para: {mail.to ?? preview.docente?.email}</p>
            <iframe
              title="Vista previa correo"
              className="w-full h-44 bg-white rounded"
              sandbox=""
              srcDoc={String(mail.html_body ?? "")}
            />
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="button" className="text-sm h-8 px-3" onClick={onAccept}>
            {acceptLabel}
          </Button>
          <Button type="button" className="text-sm h-8 px-3" variant="ghost" onClick={onSkip}>
            {skipLabel}
          </Button>
          <Button type="button" className="text-sm h-8 px-3" variant="outline" onClick={onCancel}>
            Cancelar todo
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
