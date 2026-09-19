# Что здесь функция Claude Code, а что — обходной путь

Сверено с документацией Claude Code 19 сентября 2026 года, версия Claude Code 2.1.259.

| Возможность | Статус | Роль в комплекте |
|---|---|---|
| Навыки в `.claude/skills/<name>/SKILL.md` | Функция Claude Code | Навык ставится как `.claude/skills/end/` и вызывается `/end` |
| `/context` | Встроенная команда | Показывает, чем занят контекст, цветной сеткой |
| `/usage` (алиас `/cost`) | Встроенная команда | Расход токенов сессии и аккаунта |
| `/compact [инструкции]` | Встроенная команда | Сжимает текущий чат, можно подсказать, что сохранить |
| `/clear` (алиасы `/new`, `/reset`) | Встроенная команда | Новый разговор с пустым контекстом; старый возвращается через `/resume` |
| `/autocompact` | Встроенная команда, с 2.1.221 | Порог автоматического сжатия |
| Статусная строка, поле `context_window` | Функция Claude Code | Точные `used_percentage` и `context_window_size`; `rate_limits` — только для Pro и Max |
| Хуки `UserPromptSubmit`, `PostToolUse` | Функция Claude Code | Запускают `context_watch.py` и `turn_watch.py` |
| Процент заполнения внутри хука | Обходной путь | Хуки не получают ни размер контекста, ни модель; скрипт читает запись сессии, формат которой не гарантирован |
| `SESSION_STATE.md`, `DECISIONS.md`, `TODO.md` | Архитектура комплекта | Состояние в репозитории; те же файлы читает версия навыка для Codex |

Поэтому `context_watch.py` ничего не блокирует, при ошибке молчит, а точным источником остаются
`/context` и статусная строка.

Источники:

- https://code.claude.com/docs/en/commands
- https://code.claude.com/docs/en/statusline
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/skills
