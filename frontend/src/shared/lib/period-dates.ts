/** Fechas en formato chileno dd/mm/aaaa usado por los scripts del pipeline. */

export type PeriodLike = {
  year: number;
  month_num: number;
  month_name?: string;
};

export const DATE_PARAM_NAMES = new Set(["fecha_inicio", "fecha_fin", "fecha_pago"]);

export function isDateParam(name: string): boolean {
  return DATE_PARAM_NAMES.has(name);
}

export function periodDateRange(period: PeriodLike) {
  const mm = String(period.month_num).padStart(2, "0");
  const y = period.year;
  const lastDay = new Date(y, period.month_num, 0).getDate();
  const ddLast = String(lastDay).padStart(2, "0");
  return {
    inicio: `01/${mm}/${y}`,
    fin: `${ddLast}/${mm}/${y}`,
    pago: `${ddLast}/${mm}/${y}`,
    minIso: `${y}-${mm}-01`,
    maxIso: `${y}-${mm}-${ddLast}`,
  };
}

export function clToIso(cl: string): string {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(cl.trim());
  if (!m) return "";
  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return "";
  const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const check = new Date(iso);
  if (Number.isNaN(check.getTime())) return "";
  return iso;
}

export function isoToCl(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return "";
  return `${m[3]}/${m[2]}/${m[1]}`;
}

/** Valores por defecto de fechas según paso y período seleccionado. */
export function defaultDateParamsForStage(
  stageNum: number,
  period: PeriodLike
): Record<string, string> {
  const range = periodDateRange(period);
  if (stageNum === 2) {
    return { fecha_inicio: range.inicio, fecha_fin: range.fin };
  }
  if (stageNum === 7) {
    return { fecha_pago: range.pago };
  }
  return {};
}
