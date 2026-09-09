from __future__ import annotations

import json
import sys

MAX_LABEL_CHARS = 256
MAX_TEXT_CHARS = 4096
MAX_EMIT_BYTES = 4 << 20


def clamp_str(value, limit: int = MAX_LABEL_CHARS) -> str:
    return str(value or "")[:limit]


def clamp_list(items, limit: int) -> list:
    return list(items[:limit]) if isinstance(items, (list, tuple)) else []


def emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text.encode("utf-8", errors="replace")) > MAX_EMIT_BYTES:
        text = json.dumps({"ok": False, "error": "Response exceeded size budget"})
    sys.stdout.write(text + "\n")


def fail(message: str, **extra) -> None:
    payload = {"ok": False, "error": message}
    payload.update(extra)
    emit(payload)
    raise SystemExit(0)
