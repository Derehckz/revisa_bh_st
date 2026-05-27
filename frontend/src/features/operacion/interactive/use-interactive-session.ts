import { useCallback, useEffect, useRef, useState } from "react";

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

function wsUrl(baseUrl: string, sessionId: string, apiKey: string, lastSeq: number): string {
  const base = baseUrl.replace(/^http/, "ws");
  const q = new URLSearchParams({ api_key: apiKey, last_seq: String(lastSeq) });
  return `${base}/operations/interactive/sessions/${sessionId}/stream?${q}`;
}

export function useInteractiveSession(baseUrl: string, apiKey: string) {
  const [session, setSession] = useState<SessionMeta | null>(null);
  const [events, setEvents] = useState<InteractiveEvent[]>([]);
  const [pendingPrompt, setPendingPrompt] = useState<PendingPrompt | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSeqRef = useRef(0);

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
    if (
      ev.type === "session.completed" ||
      ev.type === "session.cancelled" ||
      ev.type === "session.failed"
    ) {
      setPendingPrompt(null);
      setSession((s) => (s ? { ...s, status: ev.type.replace("session.", "") } : s));
    }
  }, []);

  const connect = useCallback(
    (sessionId: string) => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      const ws = new WebSocket(wsUrl(baseUrl, sessionId, apiKey, lastSeqRef.current));
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setError("Error de conexión WebSocket");
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
        throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`);
      }
      const meta = data as SessionMeta;
      setSession(meta);
      connect(meta.id);
      return meta;
    },
    [apiKey, baseUrl, connect]
  );

  const respond = useCallback((action: string, value?: unknown) => {
    const prompt = pendingPrompt;
    if (!prompt || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        type: "prompt.response",
        payload: { prompt_id: prompt.prompt_id, action, value },
      })
    );
    setPendingPrompt(null);
  }, [pendingPrompt]);

  const cancelSession = useCallback(async () => {
    if (!session) return;
    await fetch(`${baseUrl}/operations/interactive/sessions/${session.id}/cancel`, {
      method: "POST",
      headers: { "x-api-key": apiKey, "x-request-id": `ui-${Date.now()}` },
    });
    wsRef.current?.send(JSON.stringify({ type: "session.cancel" }));
  }, [apiKey, baseUrl, session]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return {
    session,
    events,
    pendingPrompt,
    connected,
    error,
    startSession,
    respond,
    cancelSession,
  };
}
