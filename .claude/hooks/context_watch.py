"""Напоминание о заполнении контекста для навыка end (Claude Code).

Хук на UserPromptSubmit и PostToolUse. Берёт из записи сессии (transcript) размер контекста
последнего ответа модели и сравнивает с окном модели. Порог пересечён — добавляет агенту
напоминание: сделать контрольную точку, сжать чат через /compact или вызвать /end.

Окно модели хуки не получают. Источники по порядку:
1. кэш, который пишет context_statusline.py (точное context_window_size из Claude Code);
2. переменная окружения CONTEXT_WATCH_WINDOW;
3. 200 000 токенов; если контекст уже больше — 1 000 000.

Формат transcript — не стабильный интерфейс. Поэтому скрипт ничего не блокирует, при любой
ошибке молчит, а точным источником остаются /context и статусная строка.
Только стандартная библиотека Python 3.8+.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(tempfile.gettempdir()) / "claude_context_watch"
TAIL_BYTES = 2_000_000
DEFAULT_WINDOW = 200_000
EXTENDED_WINDOW = 1_000_000

# (нижняя граница остатка в %, уровень); проверяются сверху вниз.
# Остаток < 40 / 20 / 10% = занято > 60 / 80 / 90%.
LEVELS = [(10, "handoff"), (20, "prepare"), (40, "checkpoint")]
RANK = {"normal": 0, "checkpoint": 1, "prepare": 2, "handoff": 3}

ACTIONS = {
    "checkpoint": ("Сделай контрольную точку: /compact, если задача та же, "
                   "или /end перед новым этапом."),
    "prepare": "Не начинай новый этап: доведи текущий до безопасной точки и готовь переход через /end.",
    "handoff": "Закончи текущее безопасное действие и предложи пользователю /end.",
}


def _safe(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:100]


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def last_context_tokens(transcript_path: str) -> Optional[int]:
    """Размер контекста по последнему ответу модели: input + cache_read + cache_creation.
    Та же формула, что у used_percentage в статусной строке Claude Code.
    Сжатие (/compact) сбрасывает счёт до следующего ответа."""
    path = Path(transcript_path)
    size = path.stat().st_size
    with path.open("rb") as f:
        f.seek(max(0, size - TAIL_BYTES))
        chunk = f.read().decode("utf-8", errors="replace")
    tokens = None
    for line in chunk.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue  # первая строка хвоста может быть обрезана
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("isCompactSummary") is True:
            tokens = None
            continue
        if row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        msg = row.get("message") or {}
        usage = msg.get("usage") or {}
        if not usage or msg.get("model") == "<synthetic>":
            continue
        tokens = sum(int(usage.get(k) or 0) for k in (
            "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return tokens


def context_window(session_id: str, used: int) -> int:
    cached = _load(CACHE_DIR / f"{_safe(session_id)}.window.json").get("context_window_size")
    if isinstance(cached, int) and cached > 0:
        return cached
    env = os.environ.get("CONTEXT_WATCH_WINDOW", "")
    if env.isdigit() and int(env) > 0:
        return int(env)
    return EXTENDED_WINDOW if used > DEFAULT_WINDOW else DEFAULT_WINDOW


def level_for(remaining: float) -> str:
    for bound, name in LEVELS:
        if remaining < bound:
            return name
    return "normal"


def evaluate(event: dict) -> Optional[str]:
    """Текст напоминания или None, если молчать."""
    session_id = str(event.get("session_id") or "")
    transcript = event.get("transcript_path")
    if not session_id or not transcript or not Path(transcript).is_file():
        return None
    used = last_context_tokens(transcript)
    if used is None:
        return None
    window = context_window(session_id, used)
    remaining = max(0.0, 100.0 * (window - used) / window)
    level = level_for(remaining)

    # Напоминать один раз на каждый уровень; после /compact уровень падает, и счёт идёт заново.
    # На PostToolUse (агент работает сам, без сообщений пользователя) — только крайний уровень.
    if event.get("hook_event_name") == "PostToolUse" and level != "handoff":
        return None
    state_path = CACHE_DIR / f"{_safe(session_id)}.state.json"
    warned = _load(state_path).get("level", "normal")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"level": level}), encoding="utf-8")
    if RANK[level] <= RANK.get(warned, 0):
        return None
    def num(n: int) -> str:
        return f"{n:,}".replace(",", " ")
    return (f"Контекст занят примерно на {100 - remaining:.0f}% "
            f"({num(used)} из {num(window)} токенов). {ACTIONS[level]}")


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        message = evaluate(event)
        if message:
            name = event.get("hook_event_name", "UserPromptSubmit")
            print(json.dumps({
                "systemMessage": message,
                "hookSpecificOutput": {"hookEventName": name, "additionalContext": message},
            }, ensure_ascii=False))
    except Exception:
        pass  # напоминание не должно ломать сессию
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
