"""Счётчик ходов для навыка end (Claude Code).

Хук на UserPromptSubmit. Считает ответы модели в записи сессии (transcript) и на порогах
100 / 200 / 400 ходов напоминает агенту, что сессия разрослась. Порог можно поменять
переменной окружения TURN_WATCH_THRESHOLDS, например "80,150,300".

Ход — один ответ модели. Один ответ лежит в записи сессии несколькими строками с общим
message.id (текст и каждый вызов инструмента), поэтому считаются разные message.id.
Сжатие (/compact) счётчик не сбрасывает: ходы копятся независимо от того, что осталось
в контексте. Сбрасывает только новый чат.

Читает только новые байты записи с прошлого вызова. Ничего не блокирует, при ошибке молчит.
Только стандартная библиотека Python 3.8+.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

STATE_DIR = Path(tempfile.gettempdir()) / "claude_context_watch"
DEFAULT_THRESHOLDS = (100, 200, 400)

MESSAGES = {
    0: "Ходов в сессии: {n}. Скажи пользователю и следи за заполнением контекста.",
    1: "Ходов в сессии: {n}. Пора готовиться к переходу: доведи этап до конца и "
       "предложи пользователю /end.",
    2: "Ходов в сессии: {n}. Настоятельно предложи пользователю /end и новый чат: "
       "каждый ход в таком чате дорог, а детали из середины модель держит хуже.",
}


def thresholds() -> tuple:
    raw = os.environ.get("TURN_WATCH_THRESHOLDS", "")
    try:
        values = tuple(sorted(int(x) for x in raw.split(",") if x.strip()))
        if len(values) == 3 and values[0] > 0:
            return values
    except ValueError:
        pass
    return DEFAULT_THRESHOLDS


def _state_path(session_id: str) -> Path:
    return STATE_DIR / (re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:100] + ".turns.json")


def count_turns(transcript: Path, state: dict) -> dict:
    """Дочитывает запись с сохранённого места и обновляет счётчик."""
    size = transcript.stat().st_size
    offset = state.get("offset", 0)
    if offset > size:  # файл пересоздан
        state = {}
        offset = 0
    with transcript.open("rb") as f:
        f.seek(offset)
        data = f.read()
    end = data.rfind(b"\n")
    if end == -1:
        return state
    turns = state.get("turns", 0)
    last_id = state.get("last_id")
    for line in data[:end + 1].decode("utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        msg = row.get("message") or {}
        if msg.get("model") == "<synthetic>":
            continue
        mid = msg.get("id") or row.get("uuid")
        if mid and mid != last_id:
            turns += 1
            last_id = mid
    return {**state, "offset": offset + end + 1, "turns": turns, "last_id": last_id}


def evaluate(event: dict):
    session_id = str(event.get("session_id") or "")
    transcript = event.get("transcript_path")
    if not session_id or not transcript or not Path(transcript).is_file():
        return None
    path = _state_path(session_id)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state = count_turns(Path(transcript), state)
    turns = state.get("turns", 0)
    warned = state.get("warned", -1)
    level = -1
    for i, bound in enumerate(thresholds()):
        if turns >= bound:
            level = i
    message = None
    if level > warned:  # несколько порогов разом — сообщаем только самый высокий
        message = MESSAGES[level].format(n=turns)
        state["warned"] = level
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return message


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict) and event.get("hook_event_name", "UserPromptSubmit") == "UserPromptSubmit":
            message = evaluate(event)
            if message:
                print(json.dumps({
                    "systemMessage": message,
                    "hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                           "additionalContext": message},
                }, ensure_ascii=False))
    except Exception:
        pass  # напоминание не должно ломать сессию
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
