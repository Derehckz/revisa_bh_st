/** Extrae mensaje legible de respuestas FastAPI (string o lista de errores). */
export function extractApiErrorMessage(payload: unknown, fallbackStatus: number): string {
  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    if (typeof obj.message === "string" && obj.message) {
      return obj.message;
    }
    const detail = obj.detail;
    if (typeof detail === "string" && detail) {
      return detail;
    }
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object") {
            const d = item as { msg?: string; loc?: unknown[] };
            const loc = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(".") : "";
            return loc ? `${loc}: ${d.msg ?? ""}` : String(d.msg ?? "");
          }
          return "";
        })
        .filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
  }
  return `Error HTTP ${fallbackStatus}`;
}
