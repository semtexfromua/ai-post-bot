# M4: AI-генератор постів для Telegram — Design Spec

- **Дата:** 2026-06-08
- **Статус:** затверджено до планування
- **Рівень:** спек + продакшн-практики
- **Методологія:** spec-driven → plan → TDD (test-first поюнітно)

---

## 1. Мета

Сервіс, який за розкладом (кожні 30 хв) збирає новини з сайтів і публічних
Telegram-каналів, фільтрує/дедуплікує їх, генерує через AI лаконічний пост
(емодзі + call-to-action) і публікує його в Telegram-канал. Керування джерелами,
ключовими словами, перегляд історії постів та помилок — через REST API.

---

## 2. Зафіксовані рішення (стек, версії станом на 2026-06)

| Шар | Вибір | Примітка |
|---|---|---|
| Мова | **Python 3.12** | вимога lingua-py |
| API | **FastAPI** + Uvicorn | `/docs` Swagger «з коробки» |
| Черга | **Celery 5.6.x** + **Celery Beat** | prefork-воркери |
| Брокер/стор | **Redis 7** | брокер + result backend + дедуп + lock (один сервіс) |
| БД | **PostgreSQL 16** (prod, compose) / **SQLite** (локально) | через `DATABASE_URL` |
| ORM | **SQLAlchemy 2.0 (sync)** + **Alembic** | одна `sessionmaker` для FastAPI і Celery |
| Схеми | **Pydantic v2** + **pydantic-settings** | `from_attributes=True`, `SecretStr` |
| TG читання | **Telethon 1.43.x** (юзер-сесія, read-only) | pin; 2.0 alpha не брати |
| TG публікація | **aiogram 3.2x** (Bot API) | `Bot(token, default=DefaultBotProperties(parse_mode=HTML))`; бот = адмін каналу |
| AI | **openai** SDK (sync), модель `gpt-4o-mini` через env | structured outputs + moderation |
| Парсинг сайтів | **feedparser** (RSS-first) → **httpx + selectolax + trafilatura** (fallback) | |
| Фільтр | **lingua** (uk/ru/en) + **pymorphy3** (лематизація UK/RU) | |
| Логування | **structlog** | прив'язка `news_id`/`post_id` |
| Моніторинг | **Flower** | для демо |
| Тести/lint | **pytest** + **respx** + **ruff** | sync `TestClient` + `dependency_overrides` |
| Тулінг | **uv** (deps) + **pre-commit** | `pyproject.toml` + `uv.lock` (замість requirements.txt) |

**Поділ Telegram (ключове):** Telethon — *тільки читання* публічних каналів
(незамінне: Bot API не читає чужі канали). aiogram-бот — *тільки публікація*
(офіційний, безпечний шлях; юзер-сесія лишається пасивною → мінімум ban-ризику).

---

## 3. Архітектура — процеси (docker-compose)

6 сервісів, кожен з healthcheck:

| Сервіс | Роль | Конкурентність |
|---|---|---|
| **api** | FastAPI/uvicorn. Telegram-клієнтів НЕ тримає, лише ставить таски | — |
| **worker-default** | RSS/site parse, filter, generate (OpenAI) | ~4 |
| **worker-tg** | Telethon read + aiogram publish | **=1** (один Telethon-клієнт; інакше `AuthKeyDuplicated`) |
| **beat** | розклад `*/30` | рівно 1 інстанс |
| **redis** | брокер/стор | — |
| **db** | postgres | — |
| **flower** | дашборд | — |

`depends_on: condition: service_healthy` для db/redis, щоб уникнути гонок на старті.
Міграції Alembic — окремим init-кроком до старту api.

---

## 4. Пайплайн (Celery canvas)

```
beat */30 → collect_sources (orchestrator, default-черга)
   └─ Redis-lock (SET NX EX) проти перекриття циклів
   └─ для кожного enabled Source → parse task
        • site/RSS → worker-default (feedparser conditional GET / httpx fallback)
        • tg       → worker-tg     (Telethon: resolve-once+cache, min_id інкремент)
      parse: UPSERT NewsItem з UNIQUE(content_hash) → дубль = no-op
   └─ для кожного НОВОГО NewsItem → chain(filter_item → generate_post → publish_post)
        • filter_item:  dedup(Redis seen-set) → мова(lingua) → keyword(pymorphy3 lemma)
                        не пройшов = ланцюг зупиняється
        • generate_post: OpenAI structured → moderation → length-check
                        → Post(status=generated); фейл → status=failed + error_log
        • publish_post (worker-tg, acks_late): постимо лише status==generated
                        → aiogram send → tg_message_id, status=published
                        → фейл → status=failed + error_log
```

### Жорсткі інваріанти (без них — дублі/паде)
1. **Ідемпотентна публікація:** постимо лише `Post.status == 'generated'`; зберігаємо
   `tg_message_id`; зміна статусу в тій самій транзакції; таска ключована на `post_id`.
   Другий запуск на тому ж Post → no-op.
2. **`visibility_timeout` (Redis) > найдовший `task_time_limit`** — інакше Redis тихо
   передоставляє таску другому воркеру → дубль-пост.
3. **Рівно один Beat** (не `worker -B`).
4. **`asyncio.run()` на таску** для Telethon/aiogram; без кешованих клієнтів у prefork.
5. **Без chord** (на Redis крихкий); незалежні per-item `chain`. Fan-in не потрібен.
6. Soft/hard time limits на generate/publish; `autoretry_for` + `retry_backoff` + jitter
   на OpenAI/Telegram помилки; на вичерпанні ретраїв — `status=failed`.

---

## 5. Моделі даних

4 моделі спеку + мінімальні додатки (позначені **жирним**). UUID PK через
`sqlalchemy.Uuid` (працює в SQLite і Postgres). Усі `datetime` — tz-aware UTC.

**NewsItem:** `id`, `title`, `url?`, `summary`, `source`, `published_at`, `raw_text`,
**`content_hash` (unique)** — основа дедупу/ідемпотентності парсингу.

**Post:** `id`, `news_id` (FK→NewsItem), `generated_text`,
`status` enum[`new`/`generated`/`published`/`failed`] (default `new`),
`published_at?`, **`tg_message_id?`**, **`error?`**, `created_at`.

**Source:** `id`, `type` enum[`site`/`tg`], `name`, `url` (або @username), `enabled`,
**`last_seen_msg_id?`** (Telethon інкремент), **`etag?`/`modified?`** (RSS conditional GET).

**Keyword:** `id`, `word`, **`lang?`** (опц., uk/ru/en).

**ErrorLog (нова):** `id`, `created_at`, `stage` enum[`parse`/`generate`/`publish`],
`source_id?`, `news_id?`, `post_id?`, `message`, `traceback?`. Живить «історію помилок».

---

## 6. API (FastAPI, `/docs` зі згрупованими тегами)

Версіонований префікс **`/api/v1/`** (задаток на майбутнє).

| Метод | Шлях | Призначення |
|---|---|---|
| CRUD | `/api/v1/sources` | джерела (site/tg) |
| CRUD | `/api/v1/keywords` | ключові слова/фільтри |
| GET | `/api/v1/posts` | історія постів: `{data,count}` (Page envelope) + `?status=&limit=&offset=` |
| POST | `/api/v1/generate` | поставити генерацію для `news_id` (або ad-hoc текст) → `202` + id |
| GET | `/api/v1/errors` | історія помилок (з ErrorLog) |
| GET | `/health` | healthcheck (без версії) |
| GET | `/docs` | Swagger |

- Окремі Pydantic-схеми Create / Update / Read на ресурс (Read: `from_attributes=True`).
- DB-ендпоінти — звичайні `def` (FastAPI пускає у threadpool; sync SQLAlchemy безпечний).
- `POST /api/generate` **ставить таску** (не генерує інлайн) → лишається тільки sync OpenAI.

---

## 7. Компоненти

**`ai/`** — `PostGenerator` Protocol + `OpenAIGenerator`
(`chat.completions.parse` → `PostDraft{text, language, hashtags?}`).
Промпт: стабільний system (роль/формат/«завжди українською, терміни лишай англ»/хук+чому-важливо/довжина) + user (поля NewsItem). Пост форматується кодом: екранований текст + клікабельний `<a>`-лінк на джерело + хештеги (модель URL не генерує).
`gpt-4o-mini` через env, `temperature≈0.75`, `max_completion_tokens=512` (узгоджено з
промптом «стисло, ~600 символів» — занизький кап обрізав валідні пости в
`LengthFinishReasonError`; POST_MAX_LEN=4096 лишається жорстким гардом, не ціллю генерації).
Moderation-гейт (`omni-moderation-latest`, безкоштовний) + Python-перевірка довжини
перед `generated`. У тестах — `FakeGenerator`, без мережі.

**`news_parser/`** — `BaseParser.fetch(source) -> list[NewsItem]`:
- `FeedParser` — feedparser, conditional GET (etag/modified), `published_parsed`→UTC, `bozo`→warn.
- `SiteScraper` — httpx + selectolax(lexbor) знаходить статтю, trafilatura екстрагує текст. Fallback, коли нема фіда.
- `TelegramReader` — Telethon: resolve `@username` **один раз** + кеш entity, `get_messages(min_id=last_seen_msg_id)`. Жодних join.
- Factory за `source.type`.

**`filter/`** — normalize (casefold, NFC, strip URL/emoji) → exact dedup (sha1 url + нормал. заголовок у Redis SET, TTL 7д) → мова (lingua, дозволені uk/en, **м'який** сигнал: дроп лише на високій впевненості) → keyword (pymorphy3-лема, whole-word, OR-семантика). Init detector/morph — раз на воркер.

**`telegram/`** — `publisher.py`: тонкий write-only паблішер (без Dispatcher/FSM/router).
- aiogram v3: `Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))`.
- **`async with Bot(...)`** усередині корутини (інакше «Unclosed session»); Bot створюємо **в корутині**, не на рівні модуля (aiohttp-сесія прив'язана до loop). Виклик із sync-таски — `asyncio.run(_publish(...))`.
- escape лише інтерпольованих фрагментів (`aiogram.utils.html.quote`), не всього HTML.
- error→retry мапа: `TelegramRetryAfter`→`retry(countdown=e.retry_after)`; `TelegramServerError`(5xx)→backoff; `TelegramForbidden`(втрата адмінки)/`TelegramBadRequest`(погані entities, MessageTooLong)→`failed` без retry.
- ліміт 4096 — гард в AI/format-стадії (publisher не намагається слати понад ліміт).

**`core/`** — `config.py` (pydantic-settings, вкладені моделі OpenAI/Telegram/DB,
`SecretStr` на всі секрети), `logging.py` (structlog), `db.py` (engine + sessionmaker + `get_db`).

---

## 8. Telegram safe-usage (вшити в дизайн)

**Read (Telethon, твій акаунт):**
1. Власні `api_id`/`api_hash` з my.telegram.org (хардкод-приклади банять).
2. **resolve-once + cache** entity; ніколи не re-resolve щотіку (FloodWait на тисячі сек).
3. Читати **без join**; `get_messages(min_id=...)` інкрементально.
4. **Один** підключений клієнт (worker-tg concurrency=1).
5. `StringSession` як секрет (`.env`/secret), не в git/логах.
6. `flood_sleep_threshold` default; на довгий FloodWait — sleep `e.seconds` + jitter.
7. Акаунт — розхідник: список джерел у конфізі, дизайн під заміну акаунту.

**Publish (aiogram, бот):** BotFather-токен (окремий секрет); бот = **адмін каналу**
з `can_post_messages`; `Bot(default=DefaultBotProperties(parse_mode=HTML))`.

---

## 9. Обробка помилок і логування

- Кожен `except` у пайплайні → запис у **ErrorLog** + `Post.status='failed'` (де доречно), не raise назовні.
- Стани Post змінюються в **одному** сервісному модулі (state-machine), не розкидано по тасках.
- structlog із прив'язаним контекстом (`news_id`/`post_id`) через усі етапи; JSON у контейнері.
- OpenAI: гілка на `refusal`/`None` parsed — лог + `failed`, не падіння батчу.

---

## 10. Конфіг і секрети

`pydantic-settings`, усе з `.env`. Секрети (`OPENAI_API_KEY`, `TELEGRAM_API_HASH`,
`TELETHON_STRING_SESSION`, `BOT_TOKEN`, DB-пароль) — `SecretStr`, `.get_secret_value()`
лише в місці створення клієнта. `.env` і сесії — поза git. `.env.example` у репо.

---

## 11. Тестування (TDD)

- **Acceptance-тести верхнього рівня** (зі спеки, див. §13) — скелети пишемо рано; не залежать від внутрішніх сигнатур.
- **Юніти сервісів** — TDD поюнітно під час реалізації; мок OpenAI (respx/FakeGenerator), Telethon, aiogram на межі.
- **Celery** — логіка в plain-сервісах (юніт-тести); `task_always_eager` лише для 1-2 «провід пайплайна» тестів.
- Фокус на 4 критичних шляхах: parse→dedup, generate, publish (ідемпотентність), error-logging. Не ганятись за % покриття.

---

## 12. Деплой

- **`docker compose up`** — основний шлях для ментора. README з кроками + приклади API-запитів.
- Єдиний ручний крок — Telethon-сесія: `python -m scripts.login` генерує `StringSession` → у `.env`.
  Альтернатива для демо без секретів: підняти на RSS-джерелах, TG показати в живій демо.
- **CI-lite (опційно):** GitHub Actions — ruff + pytest (services: postgres+redis) + docker build smoke.
- **CD — поза скоупом.**

---

## 13. Acceptance-критерії (основа для тестів)

1. **Sources CRUD:** create/list/update/delete Source через API працює; Read-схема не дає клієнту id/серверні поля.
2. **Keywords CRUD:** аналогічно.
3. **GET /api/posts:** повертає `{data,count}` (Page-envelope, узгоджено з контрактом); `?status=failed` фільтрує.
4. **POST /api/generate:** повертає `202` + id, ставить таску, створює Post.
5. **Parse (RSS):** дає NewsItem з title/url/summary/published_at(UTC); повторний url → новий NewsItem не створюється (UNIQUE content_hash).
6. **Filter:** айтем без збігу keyword — викидається; збіг **інфлектованою** формою (через лематизацію) — проходить; високовпевнена не-дозволена мова — дроп; уже бачений хеш (Redis) — дроп.
7. **Generate:** з NewsItem → Post(status=generated), текст непорожній і ≤ ліміту; moderation-флаг → status=failed + ErrorLog (OpenAI замокано).
8. **Publish:** постить лише status==generated; зберігає tg_message_id; **повторний запуск на тому ж Post — no-op**; фейл → status=failed + ErrorLog (aiogram замокано).
9. **Pipeline wiring (eager):** orchestrator → chain проходить end-to-end на фейках.
10. **Telethon reader:** resolve+cache раз, інкремент по min_id (замокано).
11. **Error history:** `GET /api/errors` повертає залоговані фейли.

---

## 14. Поза скоупом / future work

- **SimHash / семантичний near-dup** — лишаємо exact-дедуп; near-dup задокументовано як майбутнє (ризик хибних дропів, потребує тюнінгу на даних).
- Мультиакаунт/мультиканал, веб-UI адмінки, CD/автодеплой, async SQLAlchemy.

---

## 15. Відкриті ризики

- **ToS Telegram §1.5** забороняє агрегацію даних платформи для розробки AI — пайплайн
  «AI-пости зі скрейплених каналів» формально в сірій зоні (б'є по READ незалежно від
  способу публікації). Для навчального капстону толерується; для прод — юридична оцінка.
- Залишковий ban-ризик юзер-акаунту (нашого читача) — ненульовий навіть при read-only;
  мітигація — safe-read плейбук (§8), акаунт-розхідник.
- Telethon архівований (лют. 2026) — pin версії; запас на міграцію (Codeberg-mirror / форк).

---

## 16. Застосовані конвенції (overlay бестпрактик: zhanymkanov FastAPI BP, full-stack-fastapi-template, Celery+FastAPI)

**Структура — by-layer лишаємо** (підтверджено: by-domain пакети виправдані лише для великого моноліту; для ~5 роутерів це фрагментація).

**API:**
- Роути — звичайні **`def`** (не `async def`): стек sync, `async def` над sync-кодом блокує event loop.
- `SessionDep = Annotated[Session, Depends(get_db)]` у `app/api/deps.py`; `get_db()` — sync-генератор `with Session(engine) as s: yield s`.
- Per-resource `APIRouter(prefix, tags)` + один агрегатор `app/api/router.py`.
- Schema-тріо `{X}Create/{X}Update/{X}Read` (Read: `from_attributes=True`) + list-envelope `{X}List{data, count}`; `response_model` + `status_code` (201 на create).
- Fetch-or-404 залежність (`get_post_or_404`) лише там, де `{id}` повторюється (posts/sources); решта — інлайн `HTTPException(404)`. Без custom exception-ієрархії.

**Дані:** `MetaData(naming_convention={ix,uq,ck,fk,pk})` на `DeclarativeBase` (`app/models/base.py`) → стабільні імена констрейнтів і Alembic-autogenerate між SQLite/Postgres. Alembic `file_template` зі slug.

**Celery (`app/tasks/celery_app.py`):** standalone Celery-app (воркер не імпортує FastAPI); `task_serializer="json"`, `timezone="UTC"`, `enable_utc=True`, `broker_connection_retry_on_startup=True`, `task_ignore_result=True`, `worker_prefetch_multiplier=1`, `task_acks_late=True`, глобальні `task_soft_time_limit=120/task_time_limit=150`; `autoretry_for` **тільки** transient (HTTP/OpenAI/TelegramServerError) + `retry_backoff+jitter`, `max_retries=3` (логічні баги — fail-fast). Таски тонкі → сервіси; передаємо **ID**, перечитуємо в таску (`with SessionLocal() as s:`). `beat_schedule` — crontab у коді.
- **Черги:** мінімальний поділ `default` + `tg` (worker-tg `concurrency=1`) — виправданий Telethon single-client constraint, а не «multi-queue архітектура». Без зайвого `task_routes`.

**Тулінг:**
- **uv**: `pyproject.toml` (`[project].dependencies` + `[dependency-groups].dev`), `uv.lock`, `requires-python=">=3.12"`.
- **ruff** (`[tool.ruff]`): `target-version="py312"`, `select=["E","W","F","I","B","C4","UP"]`, **`ignore=["E501","B008","B904"]`** (B008 обов'язково — FastAPI `Depends()` у дефолтах), `exclude=["alembic"]`.
- **pre-commit** (мінімум): basic hooks + `ruff-check --fix` → `ruff-format` (порядок важливий).
- **Dockerfile**: один multi-stage uv-образ (`python:3.12-slim`, non-root, `UV_COMPILE_BYTECODE=1`, cache-mounted `uv sync --frozen`), переюзаний api/worker/beat/flower через різний `command:`.
- **conftest**: sync `TestClient` + function-scoped DB-сесія через `app.dependency_overrides[get_db]` (rollback/teardown); respx для openai/httpx; fake-publisher для aiogram.

### Refined структура проєкту
```
app/
├── api/
│   └── v1/                # версіонування (задаток на майбутнє); префікс /api/v1
│       ├── deps.py        # SessionDep, get_post_or_404 (вибірково)
│       ├── router.py      # агрегатор include_router (+ /api/v1 prefix у main.py)
│       └── routers/       # sources/keywords/posts/generate/errors — APIRouter(prefix,tags), def
│   └── (health.py — /health поза версією, для compose healthcheck)
├── core/                  # config.py (одна Settings, computed DATABASE_URL) | db.py (engine, SessionLocal, get_db) | logging.py
├── models/                # base.py (DeclarativeBase + naming_convention) | *.py ORM
├── schemas/               # base.py (APIModel: from_attributes) | *.py (Create/Update/Read/List)
├── tasks/                 # celery_app.py | parse.py | generate.py | publish.py (тонкі)
├── news_parser/           # feedparser/httpx/selectolax/trafilatura + Telethon read
├── ai/                    # sync openai SDK + 4096-гард/format
├── filter/                # lingua + pymorphy3
├── telegram/publisher.py  # тонкий write-only паблішер
└── main.py                # FastAPI + include api_router
alembic/ · tests/ · Dockerfile · docker-compose.yml · .pre-commit-config.yaml · .env.example · pyproject.toml · uv.lock
```

### Свідомо поза скоупом (overlay-скіпи, захищаємо перед ментором)
By-domain пакети · custom exception-ієрархія + handler-шар · per-module BaseSettings split · custom BaseModel з wildcard datetime-serializer · SQL-first JSON-агрегація (ламає SQLite) · async-test-client · JWT/OAuth2/CurrentUser/auth · custom `celery.Task` base · `task_routes`/multi-queue понад потрібне · DB-backed Beat (django-celery-beat) · result-dashboards/chord-canvas · `task_always_eager` для всього сьюту (мокаємо на рівні сервісів) · mypy-strict/bandit/detect-secrets у pre-commit · tox/nox-матриці · semantic-release · distroless · multi-compose/Traefik/TLS · **уся aiogram bot-framework** (Dispatcher/Router/FSM/middlewares/i18n/keyboards) — ми publish-only.
