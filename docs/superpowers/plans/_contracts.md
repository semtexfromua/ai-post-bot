# M4 — Канонічні контракти (single source of truth для плану)

> Усі задачі плану ОБОВ'ЯЗКОВО дотримуються цих сигнатур/імен. Якщо задача потребує зміни — змінюємо тут, не локально.

## Стек / версії
Python **3.12**. uv (deps) + pyproject.toml + uv.lock. ruff. pytest + respx.
FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, pydantic-settings, Alembic, Celery 5.6, redis, openai (sync), aiogram 3.2x, Telethon 1.43.x, feedparser, httpx, selectolax, trafilatura, lingua-language-detector, pymorphy3 (+dicts uk/ru), structlog, flower.

## Розкладка пакетів
```
app/
  main.py                      # FastAPI(); app.include_router(api_v1_router, prefix="/api/v1"); /health
  core/
    config.py                  # Settings (pydantic-settings)
    db.py                      # engine, SessionLocal, get_db()
    logging.py                 # configure_logging()
  models/
    base.py                    # Base, naming_convention; enums
    source.py keyword.py news_item.py post.py error_log.py
  schemas/
    base.py                    # APIModel
    source.py keyword.py post.py error_log.py generate.py common.py(Page/List envelope)
  api/
    v1/
      deps.py                  # SessionDep, get_source_or_404, get_post_or_404, Pagination
      router.py                # api_v1_router aggregator
      routers/ sources.py keywords.py posts.py generate.py errors.py
    health.py                  # /health (поза версією)
  news_parser/
    base.py                    # NewsItemData (dataclass/pydantic DTO), BaseParser
    feed.py site.py telegram_reader.py factory.py hashing.py
  filter/
    normalize.py language.py keywords.py dedup.py service.py
  ai/
    schemas.py                 # PostDraft
    generator.py               # PostGenerator Protocol, OpenAIGenerator, FakeGenerator
    moderation.py
  telegram/
    publisher.py
  tasks/
    celery_app.py              # celery_app, conf, beat_schedule
    pipeline.py                # collect_sources, parse_source, filter_item, generate_post, publish_post
    state.py                   # post status transitions + error_log writes
scripts/login.py               # Telethon StringSession mint
alembic/ tests/ Dockerfile docker-compose.yml .pre-commit-config.yaml .env.example pyproject.toml uv.lock README.md
```

## Енами (app/models/base.py)
```python
class SourceType(str, enum.Enum): site = "site"; tg = "tg"
class PostStatus(str, enum.Enum): new="new"; generated="generated"; published="published"; failed="failed"
class ErrorStage(str, enum.Enum): parse="parse"; generate="generate"; publish="publish"
```

## Base (app/models/base.py)
```python
NAMING_CONVENTION = {
  "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s",
}
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

## Моделі (SQLAlchemy 2.0 typed; UUID pk = `sqlalchemy.Uuid`, default=uuid.uuid4; усі datetime tz-aware UTC, default=lambda: datetime.now(timezone.utc))
```python
# Source (table "sources")
id: Mapped[uuid.UUID]  # pk
type: Mapped[SourceType]
name: Mapped[str]
url: Mapped[str]                       # site URL або @username для tg
enabled: Mapped[bool] = True
last_seen_msg_id: Mapped[int | None]   # Telethon інкремент
etag: Mapped[str | None]               # RSS conditional GET
modified: Mapped[str | None]
created_at: Mapped[datetime]

# Keyword (table "keywords")
id: Mapped[uuid.UUID]
word: Mapped[str]                      # unique
lang: Mapped[str | None]               # "uk"|"ru"|"en"|None

# NewsItem (table "news_items")
id: Mapped[uuid.UUID]
title: Mapped[str]
url: Mapped[str | None]
summary: Mapped[str | None]
source: Mapped[str]                    # людська назва джерела
published_at: Mapped[datetime]
raw_text: Mapped[str | None]
content_hash: Mapped[str]             # unique; sha256, основа дедупу
created_at: Mapped[datetime]

# Post (table "posts")
id: Mapped[uuid.UUID]
news_id: Mapped[uuid.UUID]            # FK news_items.id
generated_text: Mapped[str]
status: Mapped[PostStatus] = PostStatus.new
published_at: Mapped[datetime | None]
tg_message_id: Mapped[int | None]
error: Mapped[str | None]
created_at: Mapped[datetime]

# ErrorLog (table "error_logs")
id: Mapped[uuid.UUID]
created_at: Mapped[datetime]
stage: Mapped[ErrorStage]
source_id: Mapped[uuid.UUID | None]
news_id: Mapped[uuid.UUID | None]
post_id: Mapped[uuid.UUID | None]
message: Mapped[str]
traceback: Mapped[str | None]
```

## Schemas (Pydantic v2, app/schemas/)
```python
# base.py
class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# common.py  — list envelope
class Page(APIModel, Generic[T]):  # або конкретні XList класи; обираємо Generic Page[T]
    data: list[T]
    count: int

# Source: SourceCreate{type,name,url,enabled=True}; SourceUpdate{усі Optional};
#         SourceRead{id,type,name,url,enabled,created_at}
# Keyword: KeywordCreate{word,lang=None}; KeywordUpdate{word?,lang?}; KeywordRead{id,word,lang}
# Post:   PostRead{id,news_id,generated_text,status,published_at,tg_message_id,error,created_at}
# ErrorLog: ErrorLogRead{id,created_at,stage,source_id,news_id,post_id,message}
# generate.py: GenerateRequest{news_id: UUID | None = None, text: str | None = None}
#              GenerateResponse{task_id: str, post_id: UUID | None}
```

## API контракт
- Префікс `/api/v1`. Роути — **plain `def`**. `response_model` + `status_code` (201 create, 202 generate, 204 delete).
- `GET /api/v1/sources` → `Page[SourceRead]`; `POST` 201; `GET/{id}`; `PATCH/{id}`; `DELETE/{id}` 204.
- `GET /api/v1/keywords` (CRUD аналогічно).
- `GET /api/v1/posts` → `Page[PostRead]`; query `status: PostStatus | None`, `limit:int=20(le=100)`, `offset:int=0`.
- `POST /api/v1/generate` → 202 `GenerateResponse`; ставить `generate_post.delay(news_id)` (за `news_id`) або ad-hoc.
- `GET /api/v1/errors` → `Page[ErrorLogRead]`; query `stage`, limit/offset.
- `GET /health` → `{"status":"ok"}`.
- `deps.py`: `SessionDep = Annotated[Session, Depends(get_db)]`; `get_source_or_404(id, db)->Source`; `get_post_or_404(...)->Post`.

## DB (app/core/db.py)
```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if sqlite else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)
def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as s: yield s
```

## Config (app/core/config.py) — поля
`ENVIRONMENT: Literal["local","prod"]="local"`; DB: `DATABASE_URL: str` (default sqlite `sqlite:///./app.db`; у compose — postgres);
`REDIS_URL: str="redis://localhost:6379/0"`;
`OPENAI_API_KEY: SecretStr`; `OPENAI_MODEL: str="gpt-4o-mini"`; `OPENAI_TIMEOUT: int=30`;
`OPENAI_BASE_URL: str|None=None` (OpenAI-сумісний ендпоінт, напр. OpenRouter); `MODERATION_ENABLED: bool=True` (вимк. для OpenRouter — нема /moderations);
`TELEGRAM_API_ID: int`; `TELEGRAM_API_HASH: SecretStr`; `TELETHON_STRING_SESSION: SecretStr`;
`TELEGRAM_BOT_TOKEN: SecretStr`; `TELEGRAM_CHANNEL_ID: int`;
`ALLOWED_LANGUAGES: list[str]=["uk","ru","en"]`; `DEDUP_TTL_SECONDS: int=604800`; `KEYWORD_MATCH_MODE: Literal["any","all"]="any"`;
`POST_MAX_LEN: int=4096`.
`model_config = SettingsConfigDict(env_file=".env", extra="ignore")`. Інстанс `settings = Settings()`.

## news_parser контракт
```python
# base.py
@dataclass
class NewsItemData:
    title: str; url: str | None; summary: str | None
    source: str; published_at: datetime; raw_text: str | None

class BaseParser(ABC):
    @abstractmethod
    def fetch(self, source: Source) -> list[NewsItemData]: ...

# hashing.py
def content_hash(title: str, url: str | None) -> str:  # sha256 з нормалізації; основа UNIQUE
# factory.py
def get_parser(source: Source) -> BaseParser:  # site+feed→FeedParser; site→SiteScraper; tg→TelegramReader
```
- `FeedParser.fetch` — feedparser, conditional GET (source.etag/modified), published_parsed→UTC.
- `SiteScraper.fetch` — httpx GET + selectolax(lexbor) + trafilatura.
- `TelegramReader.fetch` — Telethon `asyncio.run(_read(source))`: resolve+cache, `get_messages(min_id=source.last_seen_msg_id)`; оновлює last_seen_msg_id.
- Парсери НЕ пишуть у БД; persist робить таска `parse_source`.

## filter контракт (app/filter/)
```python
def normalize(text: str) -> str                          # casefold, NFC, strip url/emoji, collapse ws
def detect_language(text: str) -> str | None             # lingua, restrict ALLOWED_LANGUAGES; None якщо невпевнено
def matches_keywords(text: str, keywords: list[Keyword], mode: str) -> bool   # pymorphy3 lemma, whole-word
def is_duplicate(content_hash: str, redis_client) -> bool                     # Redis SET NX EX(DEDUP_TTL)
def passes_filters(item: NewsItem, keywords: list[Keyword], redis_client, settings) -> bool
```
- Порядок у `passes_filters`: dedup → мова (м'який: дроп лише за впевненої не-дозволеної) → keywords.
- Детектор lingua і pymorphy-аналізатори — модуль-рівневі singleton (ініт раз).

## ai контракт (app/ai/)
```python
# schemas.py
class PostDraft(BaseModel):
    text: str; language: str; hashtags: list[str] = []
# generator.py
class PostGenerator(Protocol):
    def generate(self, news: NewsItem) -> PostDraft: ...
class OpenAIGenerator:           # holds module-level OpenAI client; .parse() structured output
    def generate(self, news: NewsItem) -> PostDraft: ...
class FakeGenerator:             # для тестів, без мережі
    def generate(self, news: NewsItem) -> PostDraft: ...
def build_generator() -> PostGenerator   # обирає OpenAI/Fake за env
# moderation.py
def is_flagged(text: str) -> bool         # omni-moderation-latest; у тестах мок
```
- Промпт: system (роль/формат/«завжди українською, терміни англ»/хук+чому-важливо/довжина ≤ POST_MAX_LEN/емодзі+CTA, без URL) + user (поля NewsItem). `format_post` додає клікабельний лінк-джерело + хештеги; publisher шле готовий HTML без повторного екранування.
- `OPENAI_MODEL`, temperature≈0.75, max_completion_tokens=512 (вистачає для стислого поста; занизький кап обрізав валідні пости). `OPENAIGenerator` ловить `LengthFinishReasonError` → чистий `ValueError`.

## telegram контракт (app/telegram/publisher.py)
```python
async def _publish(channel_id: int, text: str) -> int:    # async with Bot(...DefaultBotProperties HTML); return message_id
def publish(channel_id: int, text: str) -> int:           # asyncio.run(_publish(...))
```
- error→raise типізованих; маппінг у retry робить таска.

## tasks контракт (app/tasks/)
```python
# celery_app.py
celery_app = Celery("m4", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
# conf: task_serializer/result json, timezone UTC, enable_utc, task_ignore_result=True,
#       worker_prefetch_multiplier=1, task_acks_late=True,
#       task_soft_time_limit=120, task_time_limit=150,
#       broker_transport_options={"visibility_timeout": 3600},
#       task_routes={"app.tasks.pipeline.publish_post": {"queue":"tg"}},  # решта → default
#       beat_schedule={"collect": {"task":"app.tasks.pipeline.collect_sources","schedule": crontab(minute="*/30")}}

# pipeline.py  (усі таски — sync def, ім'я = шлях)
@celery_app.task collect_sources() -> None
    # Redis lock NX EX; для кожного enabled Source →
    # parse_source.apply_async((source_id,), queue="tg"|"default") залежно від source.type
@celery_app.task parse_source(source_id: str) -> None
    # get_parser(source).fetch(); upsert NewsItem за content_hash (дубль=skip);
    # для кожного НОВОГО → chain(filter_item.s(news_id) | generate_post.s() | publish_post.s())
@celery_app.task filter_item(news_id: str) -> str | None    # passes_filters; повертає news_id або None(стоп ланцюга)
@celery_app.task generate_post(news_id: str | None) -> str | None  # None→skip; генерація+moderation→Post(generated); повертає post_id
@celery_app.task publish_post(post_id: str | None) -> None  # None→skip; ідемпотентно: лише status==generated → publish → published+tg_message_id

# state.py
def mark_generated(db, post, text): ...
def mark_published(db, post, message_id): ...
def mark_failed(db, *, post=None, stage, message, tb=None, source_id=None, news_id=None): ...  # + ErrorLog row
```
- Ланцюг зупиняється коли таска повертає None (наступна робить early-return).
- Єдиний статичний маршрут: `publish_post → tg`. Черга для `parse_source` визначається динамічно в `collect_sources` через `apply_async(queue="tg"|"default")` залежно від типу джерела.

## Тести (tests/)
- `conftest.py`: sync `TestClient`, function-scoped Session через `app.dependency_overrides[get_db]` (rollback teardown), `fakeredis`, `respx` для openai/httpx, `FakeGenerator`, мок Telethon/aiogram.
- Дзеркалимо пакети: tests/api, tests/parser, tests/filter, tests/ai, tests/tasks.
- Acceptance-критерії зі spec §13 — кожен має тест.

## Імена черг / констант
- Черги: `default`, `tg`. Worker-tg `concurrency=1`.
- Redis lock key: `m4:lock:collect`. Dedup set key: `m4:seen` (SET NX EX per hash) або per-hash key `m4:seen:{hash}`.
