# M4 — AI-генератор постів для Telegram

Сервіс, який **кожні 30 хвилин** збирає новини з веб-сайтів/RSS та публічних Telegram-каналів,
фільтрує та дедуплікує їх, генерує через OpenAI лаконічний пост з емодзі та CTA
і автоматично публікує його у вказаний Telegram-канал.
Усім процесом можна керувати через REST API із вбудованим Swagger (`/docs`).

---

## Зміст

1. [Архітектура](#архітектура)
2. [Чому синхронний стек](#чому-синхронний-стек)
3. [Стек](#стек)
4. [Швидкий старт (docker compose)](#швидкий-старт-docker-compose)
5. [Telegram-сесія (одноразовий крок)](#telegram-сесія-одноразовий-крок)
6. [Локальна розробка (uv)](#локальна-розробка-uv)
7. [Змінні оточення](#змінні-оточення)
8. [API — приклади запитів](#api--приклади-запитів)
9. [Чек-лист функціональності](#чек-лист-функціональності)
10. [Свідомі рішення та обмеження](#свідомі-рішення-та-обмеження)

---

## Архітектура

### Процеси (docker compose)

| Сервіс | Роль | Конкурентність |
|---|---|---|
| **api** | FastAPI + Uvicorn; приймає REST-запити, ставить таски | — |
| **worker-default** | RSS/site-парсинг, фільтрація, генерація (OpenAI) | 4 |
| **worker-tg** | Telethon (читання каналів) + aiogram (публікація) | **1** (один Telethon-клієнт — інакше `AuthKeyDuplicated`) |
| **beat** | Celery Beat; `*/30` crontab → запускає `collect_sources` | 1 (рівно один інстанс) |
| **redis** | Брокер + result backend + seen-set дедуп + Redis-lock | — |
| **db** | PostgreSQL 16 | — |
| **flower** | Дашборд черг (`http://localhost:5555`) | — |
| **migrate** | Одноразовий init-сервіс: `alembic upgrade head` | — |

`depends_on: condition: service_healthy` гарантує коректний порядок запуску (db/redis → migrate → api/workers/beat).

### Пайплайн (Celery canvas)

```
beat */30 min
  └─ collect_sources  (default queue, Redis-lock SET NX EX — запобігає перекриттю циклів)
       └─ для кожного enabled Source:
            • type=site/rss  → parse_source  (worker-default)
            • type=tg        → parse_source  (worker-tg, Telethon min_id-інкремент)
          parse: UPSERT NewsItem UNIQUE(content_hash) — дубль = no-op
       └─ для кожного НОВОГО NewsItem:
            chain(
              filter_item     (worker-default) — seen-set Redis, мова lingua, keyword pymorphy3
              | generate_post (worker-default) — OpenAI structured + moderation → Post(generated)
              | publish_post  (worker-tg)      — aiogram send → tg_message_id, status=published
            )
            будь-який крок може зупинити ланцюг: не пройшов фільтр → chain зупиняється,
            помилка генерації/публікації → Post.status=failed + запис у ErrorLog
```

### Ключовий поділ Telegram

- **Telethon** (юзер-сесія, MTProto) — **читання** публічних каналів.
  Bot API фізично не може читати чужі публічні канали — тому Telethon незамінний.
- **aiogram** (Bot API) — **публікація** у власний канал.
  Бот є адміном каналу з правом `can_post_messages`; юзер-сесія лишається пасивною read-only.

---

## Чому синхронний стек

Це свідоме архітектурне рішення, а не недогляд.

**Celery prefork** запускає кожен воркер як окремий **процес** — у ньому немає event loop.
Якщо використовувати `AsyncSession` і викликати `asyncio.run()` всередині таски,
aiohttp/asyncio-пул між процесами корумпується, з'являються race conditions і падіння.

Тому обрано **sync-everywhere**:

| Шар | Рішення | Причина |
|---|---|---|
| FastAPI-роути | `def` (threadpool) | `async def` над sync-кодом блокує event loop FastAPI |
| SQLAlchemy | sync `sessionmaker` | одна `SessionLocal` для API і Celery без проблем межі async/sync |
| OpenAI у воркері | sync-клієнт | Celery prefork = без event loop |
| Telethon / aiogram | `asyncio.run()` як ізольований острівець | ці бібліотеки async-only; виклик ізольований у `asyncio.run(coro)` всередині sync-таски — без shared loop |

**Паралелізм** забезпечують Celery-воркери (процеси), а не asyncio.
Це найпростіший коректний дизайн для даного навантаження.

---

## Стек

| Шар | Бібліотека | Версія |
|---|---|---|
| API | FastAPI + Uvicorn | `^0.115` / `^0.32` |
| ORM | SQLAlchemy 2.0 (sync) + Alembic | `^2.0` / `^1.14` |
| Схеми | Pydantic v2 + pydantic-settings | `^2.9` / `^2.6` |
| Черга | Celery + Celery Beat | `^5.6` |
| Брокер/стор | Redis 7 | `^5.2` (python-клієнт) |
| TG читання | Telethon | `^1.43` (pinned) |
| TG публікація | aiogram | `^3.21` |
| AI | openai SDK (sync) | `^1.54` |
| Парсинг RSS | feedparser | `^6.0` |
| Парсинг сайтів | httpx + selectolax + trafilatura | `^0.27` / `^0.3` / `^2.0` |
| Мовний фільтр | lingua-language-detector | `^2.0` |
| Лематизація | pymorphy3 + dicts uk/ru | `^2.0` |
| Логування | structlog | `^24.4` |
| Моніторинг черг | Flower | `^2.0` |
| БД (prod) | PostgreSQL 16 | — |
| Тести | pytest + respx + fakeredis | `^8.3` / `^0.21` / `^2.26` |
| Lint/format | ruff | `^0.8` |
| Залежності | uv | — |

---

## Швидкий старт (docker compose)

### 1. Підготовка `.env`

```bash
cp .env.example .env
```

Відкрийте `.env` і заповніть усі секрети (детально — в розділі [Змінні оточення](#змінні-оточення)):

```
OPENAI_API_KEY=sk-...
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef...
TELETHON_STRING_SESSION=...   # генерується на наступному кроці
TELEGRAM_BOT_TOKEN=123456:...
TELEGRAM_CHANNEL_ID=-1001234567890
```

> **Важливо:** `docker-compose.yml` встановлює `ENVIRONMENT=prod`, що вмикає
> fail-fast валідацію `pydantic-settings`: якщо будь-який секрет порожній —
> сервіс не запуститься і одразу повідомить, яке поле відсутнє.

### 2. Генерація Telethon-сесії (якщо потрібне читання TG-каналів)

Дивіться наступний розділ [Telegram-сесія](#telegram-сесія-одноразовий-крок).

### 3. Запуск

```bash
docker compose up --build
```

Сервіс `migrate` автоматично виконає `alembic upgrade head` перед стартом `api` та воркерів.

| URL | Що відкриється |
|---|---|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/health` | Health check |
| `http://localhost:5555` | Flower (черги) |

---

## Telegram-сесія (одноразовий крок)

Telethon потребує юзер-сесії (`StringSession`) для читання публічних каналів.
Це одноразова дія:

```bash
# Локально (потрібен uv sync):
uv run python -m scripts.login

# Або через тимчасовий контейнер:
docker compose run --rm api python -m scripts.login
```

Скрипт запитає номер телефону, код підтвердження (і пароль 2FA, якщо увімкнений),
після чого виведе рядок `StringSession`. Скопіюйте його у `.env`:

```
TELETHON_STRING_SESSION=1BVtsOI8Bu...
```

> **Безпека:** для демо/капстону можна використати свій акаунт. Для продакшну
> рекомендується окремий «розхідний» акаунт (safe-read) — бот публікує через
> aiogram, тому юзер-акаунт читача лишається пасивним і ризик бану мінімальний.
> `StringSession` ніколи не потрапляє у git (`.gitignore`).

**Бот-адмін:** бот, чий токен у `TELEGRAM_BOT_TOKEN`, має бути доданий як адміністратор
каналу `TELEGRAM_CHANNEL_ID` з правом `can_post_messages` (через BotFather або налаштування каналу).

---

## Локальна розробка (uv)

```bash
# Встановити залежності
uv sync

# Запустити тести (мережево-чисті: fakeredis, respx, моки aiogram/Telethon)
uv run pytest -q
# Очікується: 165 passed

# Лінтер
uv run ruff check

# Форматування
uv run ruff format

# Міграції (SQLite за замовчуванням)
uv run alembic upgrade head
```

Для локальної розробки без Docker достатньо Redis (наприклад, `redis-server`);
БД — SQLite (`DATABASE_URL=sqlite:///./app.db`, значення за замовчуванням).

---

## Змінні оточення

Усі змінні читаються з `.env` через `pydantic-settings`.

| Змінна | Призначення | Приклад / дефолт |
|---|---|---|
| `ENVIRONMENT` | Режим: `local` (SQLite, без перевірки секретів) або `prod` (Postgres, fail-fast) | `local` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./app.db` |
| `REDIS_URL` | Redis: брокер + result backend + seen-set + lock | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | Ключ OpenAI API (SecretStr) | `sk-...` |
| `OPENAI_MODEL` | Модель для генерації постів | `gpt-4o-mini` |
| `OPENAI_TIMEOUT` | Таймаут запиту до OpenAI, секунди | `30` |
| `TELEGRAM_API_ID` | Telethon api_id з my.telegram.org (int) | `12345678` |
| `TELEGRAM_API_HASH` | Telethon api_hash з my.telegram.org (SecretStr) | `abc123...` |
| `TELETHON_STRING_SESSION` | Сесія читача (SecretStr), генерується `scripts/login.py` | `1BVtsOI8...` |
| `TELEGRAM_BOT_TOKEN` | Bot API токен від @BotFather (SecretStr) | `123456:ABC...` |
| `TELEGRAM_CHANNEL_ID` | ID каналу для публікації (int, від'ємне число) | `-1001234567890` |
| `ALLOWED_LANGUAGES` | Дозволені мови фільтра (JSON-список) | `["uk","ru","en"]` |
| `DEDUP_TTL_SECONDS` | TTL seen-set у Redis, секунди | `604800` (7 днів) |
| `KEYWORD_MATCH_MODE` | Семантика keyword-фільтра: `any` (OR) або `all` (AND) | `any` |
| `POST_MAX_LEN` | Жорсткий ліміт довжини поста (символів) | `4096` |

---

## API — приклади запитів

Базова URL: `http://localhost:8000`. Swagger: `http://localhost:8000/docs`.

Усі ендпоінти з пагінацією повертають `{"data": [...], "count": N}`.

---

### Health

```bash
GET /health
```
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### Sources (джерела)

**Список джерел**
```bash
curl "http://localhost:8000/api/v1/sources?limit=10&offset=0"
# 200 {"data":[...], "count": 2}
```

**Створити джерело (RSS/сайт)**
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"type":"site","name":"DOU","url":"https://dou.ua/rss/all.xml","enabled":true}'
# 201 {"id":"...", "type":"site", "name":"DOU", "url":"...", "enabled":true, "created_at":"..."}
```

**Створити джерело (Telegram-канал)**
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"type":"tg","name":"TechUA","url":"@techUA","enabled":true}'
# 201 {"id":"...", "type":"tg", ...}
```

**Отримати одне джерело**
```bash
curl http://localhost:8000/api/v1/sources/{source_id}
# 200 або 404
```

**Оновити джерело (часткове)**
```bash
curl -X PATCH http://localhost:8000/api/v1/sources/{source_id} \
  -H "Content-Type: application/json" \
  -d '{"enabled":false}'
# 200 {"id":"...", "enabled":false, ...}
```

**Видалити джерело**
```bash
curl -X DELETE http://localhost:8000/api/v1/sources/{source_id}
# 204 No Content
```

---

### Keywords (ключові слова фільтра)

**Список ключових слів**
```bash
curl "http://localhost:8000/api/v1/keywords?limit=20&offset=0"
# 200 {"data":[...], "count": 5}
```

**Додати ключове слово**
```bash
curl -X POST http://localhost:8000/api/v1/keywords \
  -H "Content-Type: application/json" \
  -d '{"word":"штучний інтелект","lang":"uk"}'
# 201 {"id":"...","word":"штучний інтелект","lang":"uk"}
```

**Оновити ключове слово**
```bash
curl -X PATCH http://localhost:8000/api/v1/keywords/{keyword_id} \
  -H "Content-Type: application/json" \
  -d '{"word":"AI"}'
# 200 {"id":"...","word":"AI","lang":null}
```

**Видалити ключове слово**
```bash
curl -X DELETE http://localhost:8000/api/v1/keywords/{keyword_id}
# 204 No Content
```

---

### Posts (історія постів)

```bash
# Всі пости
curl "http://localhost:8000/api/v1/posts?limit=10&offset=0"
# 200 {"data":[{"id":"...","news_id":"...","generated_text":"...","status":"published",...}], "count": 42}

# Лише провалені
curl "http://localhost:8000/api/v1/posts?status=failed"
# 200 {"data":[...], "count": 3}

# Статуси: new | generated | published | failed
```

---

### Generate (ручний запуск генерації)

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"news_id":"550e8400-e29b-41d4-a716-446655440000"}'
# 202 {"task_id":"celery-uuid...","post_id":null}
```

Або ad-hoc (без прив'язки до NewsItem):
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Довільний текст для генерації поста"}'
# 202 {"task_id":"celery-uuid...","post_id":null}
```

> Ендпоінт **ставить таску** у чергу (202 Accepted) і не чекає завершення.
> Результат з'явиться у `GET /api/v1/posts` після виконання.

---

### Errors (журнал помилок)

```bash
# Всі помилки
curl "http://localhost:8000/api/v1/errors?limit=10&offset=0"
# 200 {"data":[{"id":"...","stage":"generate","message":"...","created_at":"..."},...], "count": 7}

# Фільтр за стадією: parse | generate | publish
curl "http://localhost:8000/api/v1/errors?stage=publish"
# 200 {"data":[...], "count": 2}
```

---

## Чек-лист функціональності

Acceptance-критерії зі специфікації §13 (дизайн-документ `docs/superpowers/specs/2026-06-08-m4-ai-telegram-bot-design.md`).

| # | Функція | Реалізовано | Де (модуль / ендпоінт) |
|---|---|---|---|
| 1 | Sources CRUD: create/list/update/delete через API | ✅ | `app/api/v1/routers/sources.py`; `tests/api/test_sources.py` |
| 2 | Keywords CRUD: аналогічно Sources | ✅ | `app/api/v1/routers/keywords.py`; `tests/api/test_keywords.py` |
| 3 | `GET /api/v1/posts` → `{data, count}` + `?status=` фільтр | ✅ | `app/api/v1/routers/posts.py`; `tests/api/test_posts.py` |
| 4 | `POST /api/v1/generate` → 202 + task_id, ставить таску, створює Post | ✅ | `app/api/v1/routers/generate.py`; `tests/api/test_generate.py` |
| 5 | Parse RSS → NewsItem(title/url/summary/published_at UTC); повторний URL → UNIQUE content_hash = no-op | ✅ | `app/news_parser/feed_parser.py`; `tests/parser/test_feed_parser.py` |
| 6 | Filter: keyword (лематизація pymorphy3), мова (lingua), seen-set Redis dedup | ✅ | `app/filter/`; `tests/filter/` |
| 7 | Generate: NewsItem → Post(status=generated), текст ≤ ліміту; moderation-флаг → failed + ErrorLog | ✅ | `app/ai/`; `app/tasks/pipeline.py`; `tests/ai/` |
| 8 | Publish: лише status==generated; зберігає tg_message_id; повторний запуск → no-op; фейл → failed + ErrorLog | ✅ | `app/telegram/publisher.py`; `app/tasks/pipeline.py`; `tests/telegram/` |
| 9 | Pipeline wiring (task_always_eager): orchestrator → chain end-to-end на фейках | ✅ | `tests/tasks/test_pipeline_wiring.py` |
| 10 | Telethon reader: resolve+cache entity один раз, інкремент по min_id | ✅ | `app/news_parser/telegram_reader.py`; `tests/parser/test_telegram_reader.py` |
| 11 | `GET /api/v1/errors` повертає залоговані фейли з ErrorLog | ✅ | `app/api/v1/routers/errors.py`; `tests/api/test_errors.py` |

---

## Свідомі рішення та обмеження

### Гібрид Telethon / aiogram

Два різних Telegram-клієнти — єдиний коректний підхід:
Bot API не дозволяє читати повідомлення з публічних каналів інших авторів,
тому Telethon (MTProto, юзер-акаунт) незамінний для агрегації.
aiogram — офіційний Bot API для публікації (значно безпечніший).

### Sync-стек

Описано детально в розділі [Чому синхронний стек](#чому-синхронний-стек).
Ключовий висновок: sync є найпростішим коректним рішенням для Celery prefork
без жертви продуктивністю при даному навантаженні.

### Near-dup / SimHash — future work

Наразі реалізовано **точний** дедуп по `content_hash` (SHA1 нормалізованого заголовка + URL)
та Redis seen-set. Семантичний near-dup (SimHash / vector similarity) залишений для майбутнього:
потребує тюнінгу порогу на реальних даних, ризик хибних дропів схожих, але різних новин.

### Telethon архівований (лют. 2026)

Бібліотека Telethon переведена в архів. Версія `1.43.x` запінована в `pyproject.toml`.
Код залишається робочим; за потреби — міграція на Codeberg-дзеркало або форк.
Не брати `2.0 alpha` — нестабільна.

### ToS Telegram §1.5

Параграф 1.5 Terms of Service Telegram забороняє агрегацію даних платформи
для навчання AI без дозволу. Пайплайн «AI-пости зі скрейплених публічних каналів»
формально знаходиться у **сірій зоні** (обмеження стосується READ незалежно від
способу публікації). Для навчального капстону це толерується; для продакшн-використання
необхідна юридична оцінка.

### Залишковий ban-ризик юзер-акаунту

Read-only режим Telethon суттєво знижує ризик, але не до нуля.
Мітигація: окремий «розхідний» акаунт (safe-read), `resolve-once + cache` entity,
інкрементальне читання (`min_id`), один підключений клієнт (`worker-tg concurrency=1`),
`StringSession` поза git.
