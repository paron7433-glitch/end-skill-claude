# Установка навыка `end` для Claude Code

Корень проекта — папка, которую вы открываете в Claude Code.

1. Скопируйте `.claude/skills/end/` в корень проекта с тем же путём.
2. Скопируйте `SESSION_STATE.md`, `DECISIONS.md` и `TODO.md` из `.claude/skills/end/assets/` в
   папку `docs/` проекта. Такие файлы уже есть — не перезаписывайте. Не скопируете — навык создаст
   их сам при первом вызове.
3. Допишите текст из `CLAUDE.fragment.md` в конец `CLAUDE.md` в корне проекта. Нет файла —
   создайте.
4. Наберите `/end`. Перезапуск не нужен: Claude Code подхватывает навыки сразу. Если навык не
   появился в списке `/`, перезапустите Claude Code.

Навык можно поставить и для всех проектов сразу: `~/.claude/skills/end/` вместо
`.claude/skills/end/`.

## Необязательно: статусная строка и напоминания

Нужен Python 3.8 или новее.

**Статусная строка** показывает модель, заполнение контекста и лимиты подписки:
`Opus 5 · контекст: занято 28% · 5ч: 23% · 7д: 41%`.

1. Скопируйте `.claude/hooks/context_statusline.py` в `~/.claude/`.
2. Добавьте в `~/.claude/settings.json`:

   ```json
   "statusLine": {
     "type": "command",
     "command": "python3 ~/.claude/context_statusline.py"
   }
   ```

   В Windows вместо `python3` — `python`, а путь — полный и с прямыми слешами:
   `"command": "python C:/Users/<имя>/.claude/context_statusline.py"`. Claude Code запускает
   строку через Git Bash или PowerShell; PowerShell не раскрывает `~`, а Git Bash съедает
   обратные слеши.

**Напоминания** — два хука:

- `context_watch.py` — контекст занят больше чем на 70, 80 и 90%;
- `turn_watch.py` — в сессии 100, 200 и 400 ходов модели (свои пороги — переменная
  `TURN_WATCH_THRESHOLDS`, например `"80,150,300"`).

1. Скопируйте оба файла из `.claude/hooks/` в `.claude/hooks/` проекта.
2. Перенесите блок `hooks` из `.claude/settings.example.json` в `.claude/settings.json` проекта
   (нет файла — создайте). В Windows замените `python3` на `python`.
3. Проверьте через `/hooks`, что хуки появились.

Без статусной строки хук не знает точного размера окна модели и считает его 200 000 токенов. Если
у вас модель с окном 1 000 000, добавьте в `.claude/settings.json`:
`"env": {"CONTEXT_WATCH_WINDOW": "1000000"}`.
