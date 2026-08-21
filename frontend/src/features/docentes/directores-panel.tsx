import { useMemo, useState } from "react";
import {
  useCreateDirector,
  useDeleteDirector,
  useDirectores,
  useSeedDirectores,
  useUpdateDirector,
} from "@/shared/api/queries";
import type { DirectorPrograma } from "@/shared/api/types";
import { mapApiErrorMessage } from "@/shared/api/client";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { useToast } from "@/shared/ui/toast";

function parseSedes(raw: string): string[] {
  return raw
    .split(/[,;]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

export function DirectoresPanel({ baseUrl, apiKey }: { baseUrl: string; apiKey: string }) {
  const { push } = useToast();
  const list = useDirectores(baseUrl, apiKey);
  const create = useCreateDirector(baseUrl, apiKey);
  const update = useUpdateDirector(baseUrl, apiKey);
  const remove = useDeleteDirector(baseUrl, apiKey);
  const seed = useSeedDirectores(baseUrl, apiKey);

  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [sedes, setSedes] = useState("");

  const rows = list.data?.data || [];

  function startNew() {
    setEditingId("new");
    setNombre("");
    setEmail("");
    setSedes("");
  }

  function startEdit(row: DirectorPrograma) {
    setEditingId(row.id);
    setNombre(row.nombre || "");
    setEmail(row.email);
    setSedes(row.sedes.join(", "));
  }

  async function save() {
    const payload = {
      nombre: nombre.trim() || null,
      email: email.trim(),
      sedes: parseSedes(sedes),
      activo: "true",
    };
    try {
      if (editingId === "new") {
        await create.mutateAsync(payload);
        push("Director creado", "success");
      } else if (typeof editingId === "number") {
        await update.mutateAsync({ directorId: editingId, payload });
        push("Director actualizado. El correo se copió a los docentes de esas sedes.", "success");
      }
      setEditingId(null);
    } catch (e) {
      push(mapApiErrorMessage(e as never), "error");
    }
  }

  const busy = create.isPending || update.isPending || remove.isPending || seed.isPending;

  const hint = useMemo(
    () =>
      "Un DP puede tener varias sedes (ej. VALDIVIA, OSORNO). Si cambia el correo, se actualiza en todos los docentes de esas sedes.",
    []
  );

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Directores de programa</p>
          <p className="max-w-xl text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="h-8 px-3 text-sm"
            disabled={busy}
            onClick={() => {
              void seed.mutateAsync().then(
                (r) => push(`Cargados ${r.mapping} pares sede→correo desde BD-DOCENTES`, "success"),
                (e) => push(mapApiErrorMessage(e as never), "error")
              );
            }}
          >
            Cargar desde Excel
          </Button>
          <Button className="h-8 px-3 text-sm" disabled={busy} onClick={startNew}>
            Nuevo DP
          </Button>
        </div>
      </div>

      {editingId !== null && (
        <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-sm font-medium">{editingId === "new" ? "Nuevo director" : "Editar director"}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input placeholder="Nombre (opcional)" value={nombre} onChange={(e) => setNombre(e.target.value)} />
            <Input placeholder="Correo" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Input
              className="sm:col-span-2"
              placeholder="Sedes, separadas por coma (VALDIVIA, OSORNO)"
              value={sedes}
              onChange={(e) => setSedes(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button className="h-8 px-3 text-sm" disabled={busy || !email.trim()} onClick={() => void save()}>
              Guardar
            </Button>
            <Button variant="outline" className="h-8 px-3 text-sm" onClick={() => setEditingId(null)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {list.isLoading && <p className="text-sm text-muted-foreground">Cargando…</p>}
      {!list.isLoading && rows.length === 0 && (
        <EmptyState
          title="Sin catálogo de DP"
          description="Pulsa «Cargar desde Excel» para armarlo con los correos actuales de BD-DOCENTES, o crea uno nuevo."
        />
      )}
      <ul className="divide-y divide-border rounded-lg border border-border">
        {rows.map((row) => (
          <li key={row.id} className="flex flex-wrap items-start justify-between gap-2 px-3 py-2.5">
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium">{row.nombre || row.email}</p>
              {row.nombre ? <p className="text-xs text-muted-foreground">{row.email}</p> : null}
              <div className="flex flex-wrap gap-1">
                {row.sedes.length === 0 ? (
                  <span className="text-xs text-muted-foreground">Sin sede asignada</span>
                ) : (
                  row.sedes.map((s) => (
                    <Badge key={s}>{s}</Badge>
                  ))
                )}
              </div>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" className="h-8 px-2 text-xs" onClick={() => startEdit(row)}>
                Editar
              </Button>
              <Button
                variant="ghost"
                className="h-8 px-2 text-xs text-danger"
                disabled={busy}
                onClick={() => {
                  if (!window.confirm(`¿Quitar a ${row.email} del catálogo?`)) return;
                  void remove.mutateAsync(row.id).then(
                    () => push("Director eliminado", "success"),
                    (e) => push(mapApiErrorMessage(e as never), "error")
                  );
                }}
              >
                Quitar
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function emailDpForSede(
  directores: Array<{ email: string; sedes: string[] }>,
  sede: string
): string {
  const key = sede.trim().toUpperCase().replace(/\s+/g, " ");
  if (!key) return "";
  const hit = directores.find((d) => d.sedes.some((s) => s === key));
  return hit?.email || "";
}
