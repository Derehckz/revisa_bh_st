import { useCallback, useEffect, useRef, useState } from "react";
import { extractApiErrorMessage } from "@/shared/lib/api-error";
import { usePeriodOperationGuard } from "../period-operation-context";

export type InteractiveEvent = {
  v?: number;
  session_id?: string;
  seq: number;
  ts?: string;
  type: string;
  payload: Record<string, unknown>;
};

export type PendingPrompt = {
  prompt_id: string;
  kind: string;
  title: string;
  message: string;
  payload: Record<string, unknown>;
};

type SessionMeta = {
  id: string;
  stage_num: number;
  status: string;
  year: number;
  month: string;
};

export function isSessionRunning(status?: string | null): boolean {
  return Boolean(status) && !["completed", "cancelled", "failed"].includes(status as string);
}

function extractActiveSessionId(message: string): string | null {
  const m = /id=([a-f0-9]{8,})/i.exec(message);
  return m?.[1] ?? null;
}

function wsUrl(baseUrl: string, sessionId: string, apiKey: string, lastSeq: number): string {
  const base = baseUrl.replace(/^http/, "ws");
  const q = new URLSearchParams({ api_key: apiKey, last_seq: String(lastSeq) });
  return `${base}/operations/interactive/sessions/${sessionId}/stream?${q}`;
}

const TERMINAL_SESSION = new Set([
  "session.completed",
  "session.cancelled",
  "session.failed",
]);

export function useInteractiveSession(baseUrl: string, apiKey: string) {
  const { refreshPeriodData } = usePeriodOperationGuard();
  const refreshRef = useRef(refreshPeriodData);
  refreshRef.current = refreshPeriodData;

  const [session, setSession] = useState<SessionMeta | null>(null);
  const [events, setEvents] = useState<InteractiveEvent[]>([]);
  const [pendingPrompt, setPendingPrompt] = useState<PendingPrompt | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSeqRef = useRef(0);
  const sessionRef = useRef<SessionMeta | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualCloseRef = useRef(false);

  sessionRef.current = session;

  const appendEvent = useCallback((ev: InteractiveEvent) => {
    lastSeqRef.current = Math.max(lastSeqRef.current, ev.seq ?? 0);
    setEvents((prev) => {
      if (prev.some((e) => e.seq === ev.seq)) return prev;
      return [...prev, ev].slice(-500);
    });
    if (ev.type === "prompt.request") {
      const p = ev.payload as Record<string, unknown>;
      const inner = (p.payload as Record<string, unknown>) ?? {};
      setPendingPrompt({
        prompt_id: String(p.prompt_id ?? ""),
        kind: String(p.kind ?? "confirm"),
        title: String(p.title ?? ""),
        message: String(p.message ?? ""),
        payload: { ...inner, ...p },
      });
    }
    if (TERMINAL_SESSION.has(ev.type)) {
      setPendingPrompt(null);
      setSession((s) => (s ? { ...s, status: ev.type.replace("session.", "") } : s));
      // KPIs / estados de pasos / Excel options sin F5
      refreshRef.current();
    }
  }, []);

  const connect = useCallback(
    (sessionId: string, isReconnect = false) => {
      if (wsRef.current) {
        manualCloseRef.current = true;
        wsRef.current.close();
        manualCloseRef.current = false;
      }
      const ws = new WebSocket(wsUrl(baseUrl, sessionId, apiKey, lastSeqRef.current));
      wsRef.current = ws;
      ws.onopen = () => {
        setConnected(true);
        setError(null);
        setActiveSessionId(null);
      };
      ws.onclose = () => {
        setConnected(false);
        const active = sessionRef.current;
        if (
          !manualCloseRef.current &&
          active &&
          active.id === sessionId &&
          !TERMINAL_SESSION.has(`session.${active.status}`)
        ) {
          reconnectTimerRef.current = setTimeout(() => {
            if (sessionRef.current?.id === sessionId) {
              connect(sessionId, true);
            }
          }, 2000);
        }
      };
      ws.onerror = () => {
        if (!isReconnect) {
          setError("Error de conexión WebSocket");
        }
      };
      ws.onmessage = (msg) => {
        try {
          const ev = JSON.parse(msg.data as string) as InteractiveEvent;
          appendEvent(ev);
        } catch {
          /* ignore */
        }
      };
    },
    [apiKey, appendEvent, baseUrl]
  );

  const startSession = useCallback(
    async (stageNum: number, body: Record<string, unknown>) => {
      setError(null);
      setEvents([]);
      setPendingPrompt(null);
      lastSeqRef.current = 0;
      const res = await fetch(`${baseUrl}/operations/interactive/stages/${stageNum}/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
          "x-request-id": `ui-${Date.now()}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(
            "La API no tiene rutas interactivas (404). Reinicia uvicorn con el código actual: " +
              "python -m uvicorn api.app:app --host 127.0.0.1 --port 8000"
          );
        }
        const msg = extractApiErrorMessage(data, res.status);
        if (res.status === 409) {
          setActiveSessionId(extractActiveSessionId(msg));
        }
        throw new Error(msg);
      }
      const meta = data as SessionMeta;
      setSession(meta);
      setActiveSessionId(null);
      connect(meta.id);
      return meta;
    },
    [apiKey, baseUrl, connect]
  );

  const respond = useCallback((action: string, value?: unknown) => {
    const prompt = pendingPrompt;
    if (!prompt) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError(
        "Sin conexión en vivo con la sesión. Usa «Retomar sesión activa» o cancélala e inicia de nuevo."
      );
      return;
    }
    wsRef.current.send(
      JSON.stringify({
        type: "prompt.response",
        payload: { prompt_id: prompt.prompt_id, action, value },
      })
    );
    setPendingPrompt(null);
  }, [pendingPrompt]);

  const attachToSession = useCallback(
    async (sessionId: string) => {
      setError(null);
      setEvents([]);
      setPendingPrompt(null);
      lastSeqRef.current = 0;
      const res = await fetch(`${baseUrl}/operations/interactive/sessions/${sessionId}`, {
        headers: { "x-api-key": apiKey, "x-request-id": `ui-${Date.now()}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(extractApiErrorMessage(data, res.status));
      }
      const meta = data as SessionMeta;
      setSession(meta);
      setActiveSessionId(null);
      connect(meta.id);
      return meta;
    },
    [apiKey, baseUrl, connect]
  );

  const cancelSession = useCallback(async () => {
    if (!session) return;
    manualCloseRef.current = true;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    try {
      await fetch(`${baseUrl}/operations/interactive/sessions/${session.id}/cancel`, {
        method: "POST",
        headers: { "x-api-key": apiKey, "x-request-id": `ui-${Date.now()}` },
      });
    } catch {
      /* ignore network errors; igual liberamos la UI */
    }
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "session.cancel" }));
      }
    } catch {
      /* ignore */
    }
    wsRef.current?.close();
    setPendingPrompt(null);
    setConnected(false);
    setActiveSessionId(null);
    setSession((s) => (s ? { ...s, status: "cancelled" } : null));
    setError(null);
    refreshRef.current();
  }, [apiKey, baseUrl, session]);

  const cancelSessionById = useCallback(
    async (sessionId: string) => {
      manualCloseRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      try {
        const res = await fetch(`${baseUrl}/operations/interactive/sessions/${sessionId}/cancel`, {
          method: "POST",
          headers: { "x-api-key": apiKey, "x-request-id": `ui-${Date.now()}` },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(extractApiErrorMessage(data, res.status));
        }
      } finally {
        if (sessionRef.current?.id === sessionId) {
          wsRef.current?.close();
          setSession(null);
          setPendingPrompt(null);
          setConnected(false);
        }
        setActiveSessionId(null);
        refreshRef.current();
      }
    },
    [apiKey, baseUrl]
  );

  useEffect(() => {
    return () => {
      manualCloseRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return {
    session,
    events,
    pendingPrompt,
    connected,
    error,
    activeSessionId,
    startSession,
    attachToSession,
    cancelSessionById,
    respond,
    cancelSession,
  };
}
