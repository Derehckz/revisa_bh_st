import { useState } from "react";
import { apiPost, mapApiErrorMessage } from "@/shared/api/client";
import { useOutboxRows, useOutboxStats } from "@/shared/api/queries";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import { useToast } from "@/shared/ui/toast";
import { usePeriodOperationGuard } from "./period-operation-context";

type Props = {
  baseUrl: string;
  apiKey: string;
  disabled?: boolean;
};

export function OutboxPanel({ baseUrl, apiKey, disabled }: Props) {
  const { push } = useToast();
  const { confirmBeforeOperation, assessment } = usePeriodOperationGuard();
  const [statusFilter, setStatusFilter] = useState("");
  const [dispatchConfirm, setDispatchConfirm] = useState(false);
  const [reopenConfirm, setReopenConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const stats = useOutboxStats(baseUrl, apiKey);
  const rows = useOutboxRows(baseUrl, apiKey, statusFilter || undefined, 30);

  const blocked = disabled || assessment.isClosed;

  async function dispatchCom(dryRun: boolean) {
    if (blocked) {
      push("El período seleccionado está cerrado. Cambia de mes o usa la consola.", "error");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setBusy(true);
    try {
      const result = await apiPost<{ ok: number; failed: number; dry_skipped: number }>(
        baseUrl,
        apiKey,
        `/operations/outbox/dispatch-com?limit=30&dry_run=${dryRun}`
      );
      push(
        `Dispatch COM: ok=${result.ok}, failed=${result.failed}, omitidos=${result.dry_skipped}`,
        result.failed > 0 ? "error" : "success"
      );
      await stats.refetch();
      await rows.refetch();
    } catch (e) {
      push(mapApiErrorMessage(e as never), "error");
    } finally {
      setBusy(false);
      setDispatchConfirm(false);
    }
  }

  async function reopenFailed() {
    if (blocked) {
      push("El período seleccionado está cerrado.", "error");
      return;
    }
    if (!(await confirmBeforeOperation())) return;
    setBusy(true);
    try {
      const result = await apiPost<{ reopened: number }>(baseUrl, apiKey, "/operations/outbox/reopen-failed?limit=200");
      push(`Reabiertos ${result.reopened} registros failed → pending.`, "success");
      await stats.refetch();
      await rows.refetch();
    } catch (e) {
      push(mapApiErrorMessage(e as never), "error");
    } finally {
      setBusy(false);
      setReopenConfirm(false);
    }
  }

  const byStatus = stats.data?.by_status ?? {};

  return (
    <Card>
      <CardHeader>
        <CardTitle>Outbox de correos</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Reintento COM sin re-ejecutar scripts (misma lógica que{" "}
          <code className="text-xs">herramientas/outbox_worker.py</code>).
        </p>
        {blocked && (
          <p className="text-sm text-amber-700 rounded-md border border-amber-300 bg-amber-50 px-3 py-2">
            Período cerrado: dispatch y reapertura deshabilitados desde la web.
          </p>
        )}
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(byStatus).map(([st, n]) => (
            <span key={st} className="rounded-md border border-border px-2 py-1">
              {st}: <strong>{n}</strong>
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            Filtrar estado
            <Select className="mt-1 block" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">Todos</option>
              <option value="pending">pending</option>
              <option value="sent">sent</option>
              <option value="failed">failed</option>
            </Select>
          </label>
        </div>

        <div className="max-h-48 overflow-auto rounded-md border border-border text-xs">
          <table className="w-full">
            <thead className="sticky top-0 bg-muted">
              <tr>
                <th className="px-2 py-1 text-left">id</th>
                <th className="px-2 py-1 text-left">stage</th>
                <th className="px-2 py-1 text-left">status</th>
                <th className="px-2 py-1 text-left">attempts</th>
              </tr>
            </thead>
            <tbody>
              {(rows.data?.data ?? []).map((row) => (
                <tr key={row.id} className="border-t border-border">
                  <td className="px-2 py-1">{row.id}</td>
                  <td className="px-2 py-1 max-w-[200px] truncate" title={row.stage}>
                    {row.stage}
                  </td>
                  <td className="px-2 py-1">{row.status}</td>
                  <td className="px-2 py-1">{row.attempts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-2 border-t border-border pt-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={dispatchConfirm}
              onChange={(e) => setDispatchConfirm(e.target.checked)}
              disabled={blocked}
            />
            Confirmo ejecutar dispatch COM (hasta 30 pending)
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={busy || !dispatchConfirm || blocked}
              onClick={() => void dispatchCom(true)}
            >
              Simular dispatch
            </Button>
            <Button disabled={busy || !dispatchConfirm || blocked} onClick={() => void dispatchCom(false)}>
              Dispatch COM real
            </Button>
          </div>
        </div>

        <div className="space-y-2 border-t border-border pt-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={reopenConfirm}
              onChange={(e) => setReopenConfirm(e.target.checked)}
              disabled={blocked}
            />
            Confirmo reabrir failed elegibles como pending
          </label>
          <Button variant="outline" disabled={busy || !reopenConfirm || blocked} onClick={() => void reopenFailed()}>
            Reabrir failed
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
