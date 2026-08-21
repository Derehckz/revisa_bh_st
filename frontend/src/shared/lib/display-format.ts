/** Formato de presentación CL (montos, RUT, folios). */

function isBlank(value: unknown): boolean {
  if (value == null) return true;
  const s = String(value).trim();
  return !s || ["nan", "none", "nat", "n/a"].includes(s.toLowerCase());
}

export function formatFolio(value: unknown): string {
  if (isBlank(value)) return "";
  const n = Number(String(value).replace(",", "."));
  if (Number.isFinite(n)) return String(Math.trunc(n));
  return String(value).trim();
}

export function formatMontoCl(value: unknown): string {
  if (isBlank(value)) return "";
  let s = String(value).trim().replace(/\$/g, "").replace(/\s/g, "").replace(/\.-$/, "");
  if (s.endsWith(".") && s.indexOf(".") === s.length - 1) s = s.slice(0, -1);
  if (s.includes(",") && s.includes(".")) {
    s = s.lastIndexOf(",") > s.lastIndexOf(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  } else if (s.includes(",")) {
    const parts = s.split(",");
    if (parts.length > 1 && parts.every((p) => /^\d+$/.test(p)) && parts.slice(1).every((p) => p.length === 3)) {
      s = parts.join("");
    } else {
      s = s.replace(",", ".");
    }
  } else if (s.includes(".")) {
    const parts = s.split(".");
    if (parts.length > 1 && parts.every((p) => /^\d+$/.test(p)) && parts.slice(1).every((p) => p.length === 3)) {
      s = parts.join("");
    }
  }
  const n = Number(s);
  if (!Number.isFinite(n)) return String(value).trim();
  const body = Math.trunc(n).toLocaleString("es-CL");
  return `$${body}.-`;
}

export function formatRutCl(value: unknown): string {
  if (isBlank(value)) return "";
  let raw = String(value).trim();
  if (/^[\d.]+-[\dkK]$/.test(raw) && (raw.match(/\./g)?.length ?? 0) >= 1) return raw;
  if (/^\d+\.0+$/.test(raw)) raw = raw.split(".", 1)[0];
  else if (typeof value === "number" && Number.isInteger(value)) raw = String(value);
  const normalized = raw.replace(/[.\-\s\u00A0]/g, "").toUpperCase();
  if (normalized.length < 2) return raw.replace(/\.0$/, "");
  const dv = normalized.slice(-1);
  const cuerpo = normalized.slice(0, -1);
  const rev = cuerpo.split("").reverse().join("");
  const chunks: string[] = [];
  for (let i = 0; i < rev.length; i += 3) chunks.push(rev.slice(i, i + 3));
  const cuerpoFmt = chunks.map((c) => c.split("").reverse().join("")).reverse().join(".");
  return `${cuerpoFmt}-${dv}`;
}

export function formatDisplayField(value: unknown, kind: "folio" | "monto" | "rut" | "text" = "text"): string {
  if (isBlank(value)) return "";
  switch (kind) {
    case "folio":
      return formatFolio(value);
    case "monto":
      return formatMontoCl(value);
    case "rut":
      return formatRutCl(value);
    default:
      return String(value).trim();
  }
}
