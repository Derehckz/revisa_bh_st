type ApiError = {
  status: number;
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export function mapApiErrorMessage(error: ApiError | null): string {
  if (!error) return "";
  const statusMap: Record<number, string> = {
    401: "No autorizado: revisa tu API key.",
    422: "Solicitud inválida: revisa filtros o parámetros.",
    429: `Demasiadas solicitudes: espera ${String(error.details?.retry_after_seconds || "unos segundos")}.`,
    503: "Backend no configurado: faltan variables de seguridad en API.",
  };
  return statusMap[error.status] || `${error.code}: ${error.message}`;
}

const requestId = () => `ui-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

export async function apiGet<T>(baseUrl: string, apiKey: string, path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      "x-api-key": apiKey,
      "x-request-id": requestId(),
    },
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
      message: errorPayload?.message || "Error no controlado en API",
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
  const headers: Record<string, string> = {
    "x-api-key": apiKey,
    "x-request-id": requestId(),
  };
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
      message: errorPayload?.message || "Error no controlado en API",
      details: (errorPayload?.details || {}) as Record<string, unknown>,
    } satisfies ApiError;
  }
  return payload as T;
}
