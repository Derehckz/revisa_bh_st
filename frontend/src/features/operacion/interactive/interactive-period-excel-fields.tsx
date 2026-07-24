import { useEffect } from "react";
import type { Period, Step0OptionsResponse } from "@/shared/api/types";
import { Select } from "@/shared/ui/select";
import type { UseQueryResult } from "@tanstack/react-query";

export type PeriodExcelFieldValues = {
  monthDir: string;
  excelFile: string;
  sheet: string;
};

type Props = {
  selectedPeriod: Period;
  options: UseQueryResult<Step0OptionsResponse>;
  values: PeriodExcelFieldValues;
  onChange: (values: PeriodExcelFieldValues) => void;
  disabled?: boolean;
};

export function usePeriodExcelDefaults(
  selectedPeriod: Period,
  options: UseQueryResult<Step0OptionsResponse>
): PeriodExcelFieldValues {
  const monthDirDefault =
    options.data?.choices?.month_dir ?? `${selectedPeriod.year}/${selectedPeriod.month_name}`;
  const excelFiles = options.data?.choices?.excel_files_in_month ?? [];
  const excelDefault = excelFiles.includes("Solicitud.xlsx")
    ? "Solicitud.xlsx"
    : excelFiles[0] ?? "Solicitud.xlsx";
  const sheetOptions = options.data?.choices?.solicitud_sheets ?? [];
  const sheetDefault = String(
    options.data?.params_schema?.find((f) => f.name === "sheet")?.default ??
      options.data?.choices?.solicitud_sheet_auto ??
      sheetOptions[0] ??
      "Solicitud"
  );
  return {
    monthDir: monthDirDefault,
    excelFile: excelDefault,
    sheet: sheetDefault,
  };
}

export function InteractivePeriodExcelFields({
  selectedPeriod,
  options,
  values,
  onChange,
  disabled,
}: Props) {
  const excelFiles = options.data?.choices?.excel_files_in_month ?? [];
  const sheetOptions = options.data?.choices?.solicitud_sheets ?? [];

  return (
    <>
      <label className="block text-sm space-y-1">
        <span>Carpeta del período</span>
        <input
          type="text"
          className="w-full rounded border border-input bg-background px-2 py-1 text-sm"
          value={values.monthDir}
          onChange={(e) => onChange({ ...values, monthDir: e.target.value })}
          disabled={disabled}
          placeholder={`${selectedPeriod.year}/${selectedPeriod.month_name}`}
        />
        <p className="text-xs text-muted-foreground">
          Período: {selectedPeriod.month_name} {selectedPeriod.year}
        </p>
      </label>
      <label className="block text-sm space-y-1">
        <span>Archivo Excel</span>
        <Select
          value={values.excelFile}
          onChange={(e) => onChange({ ...values, excelFile: e.target.value })}
          disabled={disabled}
        >
          {excelFiles.length === 0 && <option value={values.excelFile}>{values.excelFile}</option>}
          {excelFiles.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </Select>
      </label>
      <label className="block text-sm space-y-1">
        <span>Hoja del Excel</span>
        <Select
          value={values.sheet}
          onChange={(e) => onChange({ ...values, sheet: e.target.value })}
          disabled={disabled}
        >
          {sheetOptions.length === 0 && <option value={values.sheet}>{values.sheet}</option>}
          {sheetOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </label>
    </>
  );
}

export function useSyncPeriodExcelDefaults(
  defaults: PeriodExcelFieldValues,
  setValues: (values: PeriodExcelFieldValues) => void
) {
  useEffect(() => {
    setValues(defaults);
  }, [defaults.monthDir, defaults.excelFile, defaults.sheet, setValues]);
}
