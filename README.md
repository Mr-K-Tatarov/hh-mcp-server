# HH MCP Server

MCP-сервер для автоматизации работы с [hh.ru](https://hh.ru) через браузерную автоматизацию (Playwright).

## Возможности

- **Поиск вакансий** — по ключевым словам, городу, зарплате, опыту, графику (удалёнка/офис/гибрид)
- **Просмотр деталей вакансий** — полное описание, требования, стек, условия
- **Управление резюме** — просмотр списка и содержимого своих резюме
- **Отклики на вакансии** — с сопроводительным письмом и ответами на вопросы работодателя
- **Отслеживание откликов** — статусы всех отправленных откликов
- **Информация о работодателях** — карточка компании

## Требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (менеджер пакетов)

## Установка

```bash
cd hh-mcp-server
uv sync
uv run playwright install chromium
```

## Авторизация

Перед первым использованием нужно авторизоваться на hh.ru:

```bash
uv run hh-mcp-server --login
```

Откроется браузер — войдите в свой аккаунт hh.ru. Сессия сохранится в `~/.hh-mcp/profile/state.json`.

## Запуск

### Как MCP-сервер (stdio, для Claude Code)

```bash
uv run hh-mcp-server
```

### С видимым браузером (для отладки)

```bash
uv run hh-mcp-server --no-headless
```

### HTTP-транспорт

```bash
uv run hh-mcp-server --transport streamable-http --port 8766
```

## Настройка в Claude Code

Добавьте в `.claude/settings.json`:

```json
{
  "mcpServers": {
    "hh": {
      "command": "/path/to/uv",
      "args": ["run", "--directory", "/path/to/hh-mcp-server", "hh-mcp-server"]
    }
  }
}
```

## MCP-инструменты

| Инструмент | Описание |
|---|---|
| `search_vacancies` | Поиск вакансий по ключевым словам (keywords, area, salary, experience, schedule) |
| `get_recommended_vacancies` | Подходящие вакансии для резюме (алгоритм hh.ru, до 1000 вакансий) |
| `get_vacancy_details` | Детали вакансии по ID |
| `get_my_resumes` | Список резюме пользователя |
| `get_resume` | Полное содержимое резюме |
| `apply_to_vacancy` | Отклик на вакансию (с письмом и ответами на вопросы) |
| `get_responses` | Статусы откликов |
| `get_employer_info` | Информация о компании |
| `close_session` | Закрытие браузера и сохранение сессии |

### Рекомендованные вакансии

Инструмент `get_recommended_vacancies` использует алгоритм hh.ru для подбора вакансий на основе резюме (аналог страницы "Подходящие вакансии"):

```
get_recommended_vacancies(
    resume_id="0fe69243ff063cb4720039ed1f574b71676a55",
    max_pages=50  # до 1000 вакансий (20 на страницу)
)
```

Это значительно точнее, чем keyword search — hh.ru анализирует опыт, навыки и должность из резюме.

### Отклик на вакансию (двухшаговый flow)

Некоторые вакансии имеют обязательные вопросы от работодателя:

1. **Первый вызов** без `question_answers` — возвращает список вопросов
2. **Второй вызов** с `question_answers` — отправляет отклик

```
# Шаг 1: получить вопросы
apply_to_vacancy(vacancy_id="12345")
# → {"status": "questions_required", "questions": [...]}

# Шаг 2: отправить с ответами
apply_to_vacancy(
    vacancy_id="12345",
    resume_id="abc123",
    cover_letter="Текст письма",
    question_answers={"task_123_text": "Ответ на вопрос"}
)
```

## Структура проекта

```
hh_mcp_server/
├── cli_main.py       # CLI точка входа (--login, --no-headless, --transport)
├── server.py         # FastMCP сервер, регистрация инструментов
├── constants.py      # URL, пути, маппинги (города, графики, опыт)
├── exceptions.py     # Кастомные исключения
├── drivers/
│   └── browser.py    # Playwright: контекст, страница, сохранение сессии
├── tools/
│   ├── vacancy.py    # Инструменты поиска и просмотра вакансий
│   ├── apply.py      # Инструмент отклика на вакансию
│   ├── resume.py     # Инструменты работы с резюме
│   ├── employer.py   # Информация о работодателе
│   └── responses.py  # Отслеживание откликов
├── scraping/
│   ├── selectors.py  # CSS-селекторы для парсинга hh.ru
│   ├── extractor.py  # Утилиты извлечения данных со страниц
│   ├── apply.py      # Логика отклика (cookies, вопросы, письмо, submit)
│   └── resume.py     # Парсинг страниц резюме
└── utils/
    └── auth.py       # Авторизация (login flow, проверка сессии)
```

## Логирование

```bash
uv run hh-mcp-server --log-level DEBUG
```

Уровни: `DEBUG`, `INFO`, `WARNING` (по умолчанию), `ERROR`.
