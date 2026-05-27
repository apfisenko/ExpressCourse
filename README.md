# ExpressCourse

Telegram-бот — **ИИ-консультант компании** «ИИ Агент». Отвечает на вопросы об услугах и курсах, ищет информацию в корпоративных PDF, проверяет актуальные факты в интернете и принимает заявки на консультацию.

![Скриншот бота](bot.jpg)

Подробнее об идее — [docs/idea.md](docs/idea.md), архитектура — [docs/vision.md](docs/vision.md).

## Возможности

| Инструмент | Назначение |
|------------|------------|
| `rag_search` | Поиск по PDF в `data/` (услуги, курсы, портфолио) |
| `web_search` | Проверка актуальных фактов через Tavily |
| `capture_lead` | Сохранение заявки в `data/leads.db` |

Роль и поведение задаются в `system.txt`.

## Переменные окружения

Скопировать `.env.example` → `.env`:

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | да | Токен бота из @BotFather |
| `OPEN_API_KEY` | да* | Ключ OpenRouter |
| `TAVILY_API_KEY` | да** | Ключ Tavily для веб-поиска |
| `EMBEDDING_MODEL` | да** | Модель эмбеддингов для RAG |
| `LANGSMITH_ENABLED` | нет | `true` — включить трейсинг |
| `LANGSMITH_API_KEY` | нет | Ключ LangSmith |
| `LANGSMITH_PROJECT` | нет | Имя проекта (дефолт: `expresscourse`) |

\* Не нужен для Ollama. \*\* Нужны для RAG и web search.

## Локальный запуск

```powershell
# Windows (PowerShell)
.\make.ps1 install
.\make.ps1 rag-index   # индексировать PDF (первый запуск)
.\make.ps1 run
```

```bash
# Linux / macOS / WSL / Git Bash
make install && make rag-index && make run
```

### RAG: индексация документов

PDF-файлы кладутся в `data/`. Индексация:

```powershell
.\make.ps1 rag-index     # только новые/изменённые PDF
.\make.ps1 rag-reindex   # полная переиндексация
```

При старте бота также выполняется инкрементальная индексация.

## Проверка (три сценария)

1. **RAG** — «Какие курсы по AI-агентам вы проводите?» → ответ с опорой на PDF.
2. **Web search** — «Какая актуальная версия LangChain?» (в контексте услуг) → ответ с источником.
3. **Lead capture** — «Хочу записаться на консультацию» → имя + контакт → подтверждение; запись в `data/leads.db`.

В LangSmith (при `LANGSMITH_ENABLED=true`) — родительский трейс `agent_handle_message` на каждый ответ, отдельный `thread_id` после `/start`.

## Ollama (локально)

```env
OPEN_BASE_URL=http://localhost:11434/v1
MODEL=llama3.2:1b
VISION_MODEL=llava:7b
AUDIO_MODEL=llama3.2:1b
```

`OPEN_API_KEY` для Ollama не нужен. Каталог моделей: [ollama.com/library](https://ollama.com/library)

## Docker

```powershell
# Windows — через WSL
.\make.ps1 docker-run
```

```bash
make docker-run
```

Перед запуском — `.env` в корне. Volume `./data` сохраняет ChromaDB и лиды между перезапусками.

## Деплой в Railway

1. Запушить репозиторий в GitHub
2. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. В **Variables** добавить:
   - `TELEGRAM_BOT_TOKEN`
   - `OPEN_API_KEY`
   - `TAVILY_API_KEY`
   - `EMBEDDING_MODEL`
   - `LANGSMITH_ENABLED`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` — рекомендуется
4. В **Settings** отключить **Public Networking** (polling, HTTP не нужен)
5. Подключить Volume для `./data` (ChromaDB + лиды)

> Одновременно может работать только один экземпляр бота с одним токеном.

Сборка по `Dockerfile`, конфиг — `railway.json`.
