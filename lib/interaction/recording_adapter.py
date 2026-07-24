"""Envuelve un adaptador y persiste eventos en JSONL."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from interaction.port import InteractionPort, PromptRequest, PromptResponse


class RecordingAdapter(InteractionPort):
    def __init__(self, inner: InteractionPort, events_path: str) -> None:
        self._inner = inner
        self._path = events_path
        os.makedirs(os.path.dirname(events_path), exist_ok=True)

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(v) for v in value]
        if isinstance(value, datetime):
            return value.isoformat()
        # numpy/pandas escalares exponen .item()
        if hasattr(value, "item"):
            try:
                return self._json_safe(value.item())
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _write(self, record: dict[str, Any]) -> None:
        record["ts"] = datetime.now(UTC).isoformat()
        safe_record = self._json_safe(record)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe_record, ensure_ascii=False) + "\n")

    def log(self, message: str, *, level: str = "info") -> None:
        self._write({"type": "log", "level": level, "message": message})
        self._inner.log(message, level=level)

    def progress(self, current: int, total: int, *, label: str = "") -> None:
        self._write({"type": "progress", "current": current, "total": total, "label": label})
        self._inner.progress(current, total, label=label)

    def table(self, title: str, rows: list[tuple[str, str]]) -> None:
        self._write({"type": "table", "title": title, "rows": rows})
        self._inner.table(title, rows)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._write({"type": event_type, "payload": payload})
        self._inner.emit(event_type, payload)

    def ask(self, request: PromptRequest) -> PromptResponse:
        self._write(
            {
                "type": "prompt.request",
                "prompt_id": request.prompt_id,
                "kind": request.kind.value,
                "title": request.title,
                "message": request.message,
                "payload": request.payload,
            }
        )
        resp = self._inner.ask(request)
        self._write(
            {
                "type": "prompt.response",
                "prompt_id": resp.prompt_id,
                "action": resp.action,
                "value": resp.value,
            }
        )
        return resp
