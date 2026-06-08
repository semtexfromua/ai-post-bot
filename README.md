# M4 — AI-генератор постів для Telegram

> **СТАТУС:** заповнюється після реалізації. Це структурний кістяк README;
> розділи нижче доповнюються фінальним текстом, прикладами та командами на
> завершальному кроці плану (post-implementation docs pass).

## Огляд

<!-- TODO(після реалізації): що це за сервіс, що робить за розкладом, як збирає
новини, фільтрує, генерує AI-пост і публікує в Telegram-канал. Керування через REST. -->

## Чому sync-стек (нотатка)

<!-- TODO(після реалізації): пояснити свідомий вибір sync SQLAlchemy/FastAPI def-роутів
+ sync OpenAI у Celery-тасках; чому async тут не дає виграшу і ускладнює. -->

## Швидкий старт

<!-- TODO(після реалізації):
1. cp .env.example .env та заповнити секрети
2. uv run python -m scripts.login → TELETHON_STRING_SESSION у .env
3. docker compose up --build
4. відкрити http://localhost:8000/docs та http://localhost:5555 (flower)
-->

## Змінні середовища

<!-- TODO(після реалізації): таблиця env-змінних. -->

| Змінна | Тип | За замовчуванням | Опис |
|---|---|---|---|
| `ENVIRONMENT` | `local`/`prod` | `local` | режим |
| `DATABASE_URL` | str | `sqlite:///./app.db` | БД (postgres у compose) |
| `REDIS_URL` | str | `redis://localhost:6379/0` | брокер/стор/дедуп/lock |
| `OPENAI_API_KEY` | secret | — | ключ OpenAI |
| `OPENAI_MODEL` | str | `gpt-4o-mini` | модель |
| `OPENAI_TIMEOUT` | int | `30` | таймаут OpenAI, сек |
| `TELEGRAM_API_ID` | int | — | Telethon api_id |
| `TELEGRAM_API_HASH` | secret | — | Telethon api_hash |
| `TELETHON_STRING_SESSION` | secret | — | сесія читача (scripts/login.py) |
| `TELEGRAM_BOT_TOKEN` | secret | — | BotFather-токен паблішера |
| `TELEGRAM_CHANNEL_ID` | int | — | цільовий канал публікації |
| `ALLOWED_LANGUAGES` | list | `["uk","ru","en"]` | мовний фільтр |
| `DEDUP_TTL_SECONDS` | int | `604800` | TTL seen-set, сек |
| `KEYWORD_MATCH_MODE` | `any`/`all` | `any` | семантика keyword-фільтра |
| `POST_MAX_LEN` | int | `4096` | ліміт довжини поста |

## Приклади API

<!-- TODO(після реалізації): curl-приклади для
- POST /api/v1/sources, GET /api/v1/sources
- POST /api/v1/keywords
- GET /api/v1/posts?status=failed
- POST /api/v1/generate
- GET /api/v1/errors
- GET /health
-->

## Відповідність acceptance-критеріям (§13 спеки)

<!-- TODO(після реалізації): таблиця 1..11 критерій → тест(и), що його покривають. -->

| # | Критерій | Тести |
|---|---|---|
| 1 | Sources CRUD | TODO |
| 2 | Keywords CRUD | TODO |
| 3 | GET /api/posts envelope + ?status | TODO |
| 4 | POST /api/generate 202 + Post | TODO |
| 5 | Parse RSS + UNIQUE content_hash | TODO |
| 6 | Filter (dedup/мова/keyword-лема) | TODO |
| 7 | Generate → Post(generated)/moderation→failed | TODO |
| 8 | Publish idempotent + tg_message_id | TODO |
| 9 | Pipeline wiring (eager) | TODO |
| 10 | Telethon reader resolve+cache/min_id | TODO |
| 11 | Error history GET /api/errors | TODO |

## Архітектура

<!-- TODO(після реалізації): діаграма процесів (api, worker-default, worker-tg,
beat, redis, db, flower), Celery-canvas пайплайн, поділ Telethon(read)/aiogram(publish),
жорсткі інваріанти ідемпотентності. -->
