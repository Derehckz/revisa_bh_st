import type { StageParamField } from "@/shared/api/types";
import { isDateParam } from "@/shared/lib/period-dates";
import { DateInput } from "@/shared/ui/date-input";
import { Select } from "@/shared/ui/select";
import type { Period } from "@/shared/api/types";
import { periodDateRange } from "@/shared/lib/period-dates";

type Props = {
  schema: StageParamField[];
  params: Record<string, unknown>;
  setField: (name: string, value: unknown) => void;
  disabled?: boolean;
  selectedPeriod?: Period;
};

export function StageParamFields({ schema, params, setField, disabled, selectedPeriod }: Props) {
  const periodDates = selectedPeriod ? periodDateRange(selectedPeriod) : null;

  return (
    <div className="space-y-3">
      {schema.map((field) => {
        if (field.type === "info" || field.name.startsWith("_ui_")) {
          return (
            <p key={field.name} className="rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-sm text-blue-900">
              {String(field.default ?? field.label)}
            </p>
          );
        }

        if (field.type === "boolean") {
          return (
            <label
              key={field.name}
              className="flex items-start gap-2 rounded-md border border-border p-3 text-sm cursor-pointer hover:bg-muted/40"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={Boolean(params[field.name])}
                onChange={(e) => setField(field.name, e.target.checked)}
                disabled={disabled}
              />
              <span>
                <span className="font-medium">{field.label}</span>
                {field.help && <span className="block text-xs text-muted-foreground mt-0.5">{field.help}</span>}
              </span>
            </label>
          );
        }

        if (
          field.type === "select" ||
          field.type === "select_sheet" ||
          field.type === "select_path" ||
          field.type === "select_maestro" ||
          field.type === "select_bd"
        ) {
          const opts = field.options ?? [];
          return (
            <div key={field.name} className="space-y-1">
              <p className="text-sm font-medium">
                {field.label}
                {field.required ? " *" : ""}
              </p>
              <Select
                value={String(params[field.name] ?? "")}
                onChange={(e) => setField(field.name, e.target.value)}
                disabled={disabled || opts.length === 0}
              >
                {opts.length === 0 && <option value="">(no hay opciones — revisa la carpeta del mes)</option>}
                {opts.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
            </div>
          );
        }

        if (isDateParam(field.name)) {
          return (
            <div key={field.name} className="space-y-1">
              <p className="text-sm font-medium">
                {field.label}
                {field.required ? " *" : ""}
                {selectedPeriod && (
                  <span className="font-normal text-muted-foreground">
                    {" "}
                    ({selectedPeriod.month_name} {selectedPeriod.year})
                  </span>
                )}
              </p>
              <DateInput
                value={String(params[field.name] ?? "")}
                onChange={(v) => setField(field.name, v)}
                disabled={disabled}
                minIso={periodDates?.minIso}
                maxIso={periodDates?.maxIso}
                placeholder={field.help || "dd/mm/aaaa"}
              />
            </div>
          );
        }

        return (
          <div key={field.name} className="space-y-1">
            <p className="text-sm font-medium">
              {field.label}
              {field.required ? " *" : ""}
            </p>
            <input
              className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
              value={String(params[field.name] ?? "")}
              onChange={(e) => setField(field.name, e.target.value)}
              placeholder={field.help || ""}
              disabled={disabled}
            />
          </div>
        );
      })}
    </div>
  );
}

export function buildConfirmSummary(
  schema: StageParamField[],
  params: Record<string, unknown>
): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  for (const f of schema) {
    if (f.type === "info" || f.name.startsWith("_ui_")) continue;
    const v = params[f.name];
    if (f.type === "boolean") {
      if (v) rows.push({ label: f.label, value: "Sí" });
      continue;
    }
    if (v !== "" && v !== undefined && v !== null) {
      rows.push({ label: f.label, value: String(v) });
    }
  }
  return rows;
}
