import { extractApiErrorMessage } from "@/shared/lib/api-error";

export type ApiError = {
  status: number;
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export function mapApiErrorMessage(error: ApiError | null): string {
  if (!error) return "";

  const validationHint = formatValidationDetails(error.details);
  if (error.status === 422) {
    // Preferir el detalle del backend (p. ej. "Maestro rechazado…") sobre el genérico.
    const msg = (error.message || "").trim();
    if (msg && !isGeneric422Message(msg)) {
      return validationHint ? `${msg}: ${validationHint}` : msg;
    }
    if (validationHint) return validationHint;
    return "Solicitud inválida: revisa filtros o parámetros.";
  }

  const statusMap: Record<number, string> = {
    401: "No autorizado: revisa tu API key.",
    429: `Demasiadas solicitudes: espera ${String(error.details?.retry_after_seconds || "unos segundos")}.`,
    503: "Backend no configurado: faltan variables de seguridad en API.",
  };
  if (statusMap[error.status]) return statusMap[error.status];
  if (error.message) return error.message;
  return `${error.code}: error ${error.status}`;
}

function isGeneric422Message(message: string): boolean {
  const n = message
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return (
    n === "parametros de entrada invalidos" ||
    n.startsWith("solicitud invalida: revisa filtros")
  );
}

function formatValidationDetails(details: Record<string, unknown> | undefined): string {
  if (!details) return "";
  const errors = details.errors;
  if (!Array.isArray(errors) || errors.length === 0) return "";
  const parts = errors
    .slice(0, 4)
    .map((item) => {
      if (typeof item === "string") return item;
      if (!item || typeof item !== "object") return "";
      const row = item as { msg?: string; loc?: unknown[]; message?: string };
      const loc = Array.isArray(row.loc)
        ? row.loc.filter((x) => x !== "body" && x !== "query" && x !== "path").join(".")
        : "";
      const msg = row.msg || row.message || "";
      return loc ? `${loc}: ${msg}` : String(msg);
    })
    .filter(Boolean);
  return parts.join("; ");
}

const OPERATOR_KEY = "bh_operator_name";

const requestId = () => `ui-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

export function getOperatorName(): string {
  try {
    return (localStorage.getItem(OPERATOR_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function setOperatorName(name: string): void {
  try {
    localStorage.setItem(OPERATOR_KEY, name.trim());
  } catch {
    /* ignore */
  }
}

function authHeaders(apiKey: string): Record<string, string> {
  const headers: Record<string, string> = {
    "x-api-key": apiKey,
    "x-request-id": requestId(),
  };
  const operator = getOperatorName();
  if (operator) headers["x-operator-name"] = operator;
  return headers;
}

export async function apiGet<T>(baseUrl: string, apiKey: string, path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: authHeaders(apiKey),
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const errorPayload = payload as Partial<ApiError> | null;
    throw {
      status: response.status,
      code: errorPayload?.code || `HTTP_${response.status}`,
      message: errorPayload?.message || extractApiErrorMessage(payload, response.status),
      details: (errorPayload?.details || {}) as Record<string, unknown>,
    } satisfies ApiError;
  }
  return payload as T;
}

export async function apiPost<T>(
  baseUrl: string,
  apiKey: string,
  path: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = authHeaders(apiKey);
  const init: RequestInit = { method: "POST", headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${baseUrl}${path}`, init);
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const errorPayload = payload as Partial<ApiError> | null;
    throw {
      status: response.status,
      code: errorPayload?.code || `HTTP_${response.status}`,
      message: errorPayload?.message || extractApiErrorMessage(payload, response.status),
      details: (errorPayload?.details || {}) as Record<string, unknown>,
    } satisfies ApiError;
  }
  return payload as T;
}

export async function apiRequest<T>(
  baseUrl: string,
  apiKey: string,
  path: string,
  method: "PUT" | "DELETE",
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = authHeaders(apiKey);
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${baseUrl}${path}`, init);
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const errorPayload = payload as Partial<ApiError> | null;
    throw {
      status: response.status,
      code: errorPayload?.code || `HTTP_${response.status}`,
      message: errorPayload?.message || extractApiErrorMessage(payload, response.status),
      details: (errorPayload?.details || {}) as Record<string, unknown>,
    } satisfies ApiError;
  }
  return payload as T;
}

/** POST multipart/form-data (no Content-Type manual — el browser pone el boundary). */
export async function apiUpload<T>(
  baseUrl: string,
  apiKey: string,
  path: string,
  form: FormData
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      ...authHeaders(apiKey),
    },
    body: form,
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const errorPayload = payload as Partial<ApiError> | null;
    throw {
      status: response.status,
      code: errorPayload?.code || `HTTP_${response.status}`,
      message: errorPayload?.message || extractApiErrorMessage(payload, response.status),
      details: (errorPayload?.details || {}) as Record<string, unknown>,
    } satisfies ApiError;
  }
  return payload as T;
}
