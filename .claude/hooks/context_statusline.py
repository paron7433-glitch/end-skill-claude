"""Статусная строка Claude Code: модель, заполнение контекста, лимиты подписки.

Пример вывода:  Opus 5 · контекст: занято 28% · 5ч: 23% · 7д: 41%

Числа берутся из JSON, который Claude Code передаёт статусной строке:
context_window.used_percentage и rate_limits (лимиты есть только у подписок Pro и Max).
Заодно кладёт размер окна модели в кэш — его читает context_watch.py.
Только стандартная библиотека Python 3.8+.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

CACHE_DIR = Path(tempfile.gettempdir()) / "claude_context_watch"


def _pct(value) -> str:
    return f"{float(value):.0f}%"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        data = json.load(sys.stdin)
    except Exception:
        print("")
        return 0

    parts = [str((data.get("model") or {}).get("display_name") or "Claude")]

    ctx = data.get("context_window") or {}
    used = ctx.get("used_percentage")
    parts.append(f"контекст: занято {_pct(used)}" if used is not None else "контекст: —")

    limits = data.get("rate_limits") or {}
    for key, label in (("five_hour", "5ч"), ("seven_day", "7д")):
        spent = (limits.get(key) or {}).get("used_percentage")
        if spent is not None:
            parts.append(f"{label}: {_pct(spent)}")

    print(" · ".join(parts))

    size = ctx.get("context_window_size")
    session_id = str(data.get("session_id") or "")
    if isinstance(size, int) and size > 0 and session_id:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:100]
            (CACHE_DIR / f"{safe}.window.json").write_text(
                json.dumps({"context_window_size": size}), encoding="utf-8")
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
