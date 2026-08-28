# Stage 9 — The kernel: `core` grows its own four layers

> **Status: not started.**

**Goal:** `app/core/` stops being a drawer of six flat modules and becomes the shared kernel every
feature module extends — `BaseEntity`, `IBaseRepository`, `BaseFilter`, `BaseUseCase` and its CRUD
subclasses, `BaseService`, `BaseTable`, `BaseRepositoryPostgres` — laid out in the same four layers
the modules use. Nothing under `app/modules/` changes, so the wire contract is unchanged by
construction.

Stage 8 gave every module four directories. Two of them are still empty. That is not an oversight
being corrected here — it is that there was nothing for a module's `application/` layer to be *made
of*. A use case with no base class is a function, and a repository with no base class is a query
written twice. This stage builds the pieces; Stages 10–12 slice each module onto them.

The shape is taken from [`dfiallo35/property-management`](https://github.com/dfiallo35/property-management),
which runs the same vertical-slice-over-a-shared-`core` layout across fourteen features. Where this
plan deviates from it, the deviation is named and justified — see **Deviations from the reference**
below. Copying a layout without the reasons is how a codebase ends up with scaffolding it cannot
explain.

**Prerequisite:** Stage 8 checkpoint passes.

## The target layout

```
api/app/
├── main.py                          # unchanged path — `app.main:app` is the ASGI entrypoint
├── seed.py                          # unchanged path — `python -m app.seed` is in three docs
└── core/
    ├── config.py                    # stays flat: config is read by every layer and belongs to none
    ├── domain/
    │   ├── models.py                # EmptyEntity · BaseEntity
    │   ├── interfaces.py            # IBaseRepository · IRateLimiter
    │   ├── filters.py               # BaseFilter — the _eq/_in/_ilike/_gte/_lte convention
    │   ├── exceptions.py            # BaseError(status_code, code, message) · NotFoundError
    │   └── enums.py                 # UseCaseEnum
    ├── application/
    │   ├── dtos.py                  # BaseCreateRequest · BaseUpdateRequest · BaseOutput
    │   │                            # BasePaginatedOutput · FieldError · ErrorBody  ← errors.py
    │   ├── mappers.py               # BaseMapper — to_api / to_domain / to_update
    │   ├── use_cases.py             # BaseUseCase + Create/Update/Delete/List/Paginate/GetById
    │   └── services.py              # BaseService — mapper + filter_class + init_use_cases
    ├── infrastructure/
    │   ├── postgres/
    │   │   ├── database.py          # ← core/db.py    engine · get_session
    │   │   ├── tables.py            # BaseTable · UTCDateTime
    │   │   ├── mappers.py           # BaseMapper — to_table / to_domain
    │   │   └── repositories.py      # BaseRepositoryPostgres — create/list/count/update/delete/filter
    │   └── ratelimit.py             # ← core/ratelimit.py, now behind IRateLimiter
    └── presentation/
        ├── app.py                   # create_app — CORS, handlers, telemetry, routers
        ├── errors.py                # ← core/errors.py, handler half only
        ├── filters.py               # BaseFilter (query-param model) with .to_domain()
        └── telemetry.py             # ← core/telemetry.py — it installs middleware, so it is presentation
```

`core/revalidate.py` is not in that tree. It is the cache invalidator, and the thing being
invalidated is the catalog — so it moves into the `catalog` module in Stage 10, not into `core`.
A thing belongs in `core` only if more than one module uses it *or* it names no module's
vocabulary, and `revalidate` fails both tests.

## Steps

1. **Move what already exists, without touching it.** `db.py`, `ratelimit.py`, `telemetry.py`, and
   the handler half of `errors.py` go to their layers above. `errors.py` splits: `FieldError`,
   the error body model and `error_response` are the wire contract and land in
   `core/application/dtos.py`; `http_error_handler` and `validation_error_handler` name `fastapi`
   and land in `core/presentation/errors.py`. Import churn only — no logic moves in this step.

2. **`core/domain/models.py`.** `EmptyEntity(BaseModel)` with `to_dict(exclude_none=False)`, and
   `BaseEntity(EmptyEntity)` adding `id: int | None`, `created_at`, `updated_at`. **Pure pydantic —
   no `sqlmodel`, no `sqlalchemy`.** This is the class that makes the rest of the migration possible,
   and the reason Stage 10 can turn on a domain-forbids-persistence contract that today would fail
   on every entity in the service.

   Integer primary keys, not the reference's UUIDs. Slugs and quote refs are this service's public
   identifiers; the integer key is never serialized and swapping it would be a migration with no
   reader.

3. **`core/domain/filters.py`.** `BaseFilter` carrying `limit`, `offset`, `order_by`, `id_eq`,
   `created_at_gte/lte`, `updated_at_gte/lte`, with the naive-datetime-is-UTC validator from the
   reference — a date-only query param must not have its boundary decided by the host's timezone.
   The `_eq` / `_in` / `_ilike` / `_gte` / `_lte` suffix convention is load-bearing from here on:
   repository `filter()` overrides key off these names.

4. **`core/domain/interfaces.py`.** `IBaseRepository` (ABC) with `create` · `list` · `count` ·
   `update` · `delete`, and `IRateLimiter` with `check(key)`. ABCs rather than `Protocol`s, matching
   the reference: the base repository is *inherited* here, not merely satisfied, so the ABC is
   carrying its own weight.

5. **`core/domain/exceptions.py`.** `BaseError(Exception)` carrying `status_code`, a stable `code`,
   and a message; `NotFoundError`. Domain code raises these; nothing in `domain/` or `application/`
   ever names `HTTPException` again. `core/presentation/errors.py` gains a handler rendering
   `BaseError` into the existing error envelope, so the wire shape does not move.

   No i18n. The reference renders every message through a Spanish/English catalog; this site is
   English-only and [decisions.md](../decisions.md) defers i18n explicitly. Messages stay literal.

6. **`core/application/`.** `dtos.py` (`BaseCreateRequest`, `BaseUpdateRequest`, `BaseOutput`,
   `BasePaginatedOutput[T]` with `items`/`total`/`limit`/`offset`); `mappers.py` (`BaseMapper` ABC —
   `to_api` / `to_domain` / `to_update`); `use_cases.py`; `services.py`.

   `BaseUseCase` is the reference's template method: `pre_run → validate → run → post_run`, driven
   by `exec`. `CreateUseCase`, `UpdateUseCase`, `BatchUpdateUseCase`, `DeleteUseCase`, `ListUseCase`,
   `PaginateUseCase` and `GetByIdUseCase` implement it for the standard shapes. Features override
   *hooks*, never `exec`.

   Five of this service's eight endpoints land on one of those subclasses (see the table in
   [Stage 10](10-catalog-slice.md)). `UpdateUseCase`, `DeleteUseCase` and `BatchUpdateUseCase` will
   have **no caller** when this migration finishes — the catalog is seeded, not edited over HTTP,
   and a lead is never mutated. Mark them `# pragma: no cover` with a comment saying so, the way the
   reference marks its own unreached `BatchUpdateUseCase`. Scaffolding that lies about being used is
   worse than scaffolding that admits it.

   `BaseService` requires subclasses to set `mapper` and `filter_class` before `super().__init__()`,
   then builds `self.use_cases` keyed by `UseCaseEnum` via `init_use_cases(deps)`.

7. **`core/infrastructure/postgres/`.** `tables.py` gets `BaseTable` — `id`, `created_at`,
   `updated_at` — plus the reference's `UTCDateTime` type decorator, which normalizes a naive
   datetime to UTC at the bind boundary so a backfill or a factory is not silently
   timezone-dependent on the machine that ran it. `mappers.py` gets the table↔domain `BaseMapper`
   ABC (`to_table` / `to_domain`) — deliberately a *different* mapper from the application one,
   because domain↔DTO and domain↔table are different jobs that drift apart.

   `repositories.py` gets `BaseRepositoryPostgres(IBaseRepository)` with class attributes `mapper`
   and `table_class`, and a `filter(filters, query) -> Select` hook applying the common filters,
   ordering, and `limit`/`offset`. An unknown `order_by` raises `NotValidOrderBy` rather than being
   ignored — a silently ignored sort is a page that looks right and is not.

8. **`core/presentation/filters.py`.** A second `BaseFilter`, a pydantic model of *query
   parameters*, with `domain_filter_class` as a `ClassVar` and a `to_domain()` that constructs it.
   Two filter classes for one concept looks redundant until the first time a query param needs a
   bound (`le=100`) or an alias that the domain has no opinion about. This is where `MAX_PAGE_SIZE`
   ends up living in Stage 12.

9. **`core/presentation/app.py`.** `create_app(title, router)` assembling CORS, the exception
   handlers, telemetry, and the router — with `app/main.py` reduced to building the root router and
   calling it. **`app.main:app` must remain importable at that exact path**: it is what
   `vercel.json`, the Dockerfile, and `docker compose` all name.

10. **One migration: `created_at` / `updated_at` on every table.** `BaseTable` mandates them, so
    `platform`, `optiongroup`, `option`, `optionrule`, `asset` and `quoteline` each gain two
    columns with a `server_default` of `now()`. `quote.created_at` **already exists, indexed, and
    is ordered on by the admin list** — the migration must leave that column and its index alone
    rather than dropping and recreating them. Use the **alembic-migration** skill; autogenerate gets
    server defaults wrong often enough that reading the revision is part of the job.

11. **Contracts.** Add a `Layers within core` contract — `presentation | infrastructure` →
    `application` → `domain`, the same rule the modules already carry. `core` is now a module in
    every respect except that everything may import it.

## Deviations from the reference, and why

| Reference | Here | Why |
|---|---|---|
| `dependency_injector` `Container` of `Singleton`s, `@inject` + `Provide[...]` | FastAPI `Depends`, one `presentation/dependencies.py` per module | Same seam for tests (`dependency_overrides`), no second DI system beside the framework's, no `wire()` list to keep in sync. The composition root stays where FastAPI can see it. |
| Async SQLAlchemy 2.0 + `asyncpg`, `DbConnection.get_session()` opening a session per repository call | Sync SQLModel + `psycopg`, request-scoped `Depends(get_session)` injected into the repository | The service is sync today and the quote submission needs one transaction across the ref-retry. Async is a separate change with its own risk, not a rider on a layering refactor. |
| `page` / `size` on the filter, `pages` on the output | `limit` / `offset` on both | `GET /v1/admin/quotes` already takes `limit`/`offset` and the admin page already reads them. The wire contract does not move for a naming preference. |
| Plain SQLAlchemy `DeclarativeBase` tables | SQLModel tables (`class PlatformTable(BaseTable, table=True)`) | A SQLModel table class *is* a SQLAlchemy declarative model; once entities are separate, keeping it costs nothing and swapping it would churn Alembic and the test harness for no boundary gain. `SQLModel.metadata` stays what Alembic and `tests/test_entity_registry.py` read. |
| i18n catalogs on every exception | Literal English messages | [decisions.md](../decisions.md) defers i18n. |
| Tests colocated at `features/<name>/tests/` | `api/tests/modules/<name>/` | Already mirrors the module tree, and keeps tests out of the shipped package. |

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                        # "Layers within core" now active
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q
uv run uvicorn app.main:app --port 8000 &  # the ASGI path must not have moved

curl -s localhost:8000/healthz
curl -s localhost:8000/v1/catalog | jq -S . > /tmp/catalog.before.json
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . > /tmp/platform.before.json
curl -s localhost:8000/v1/catalog | jq -S . | diff /tmp/catalog.before.json -
```

Capture those two golden files here and keep them: Stages 10–13 diff against them, and this is the
last stage in which the response bodies are produced by code nobody has restructured.

New unit tests, none of which need a running module:

- `tests/core/test_filters.py` — `limit`/`offset` passthrough, the naive-datetime-is-UTC validator.
- `tests/core/test_use_cases.py` — `exec` calls the four hooks in order, and a subclass overriding
  `validate` can abort before `run` touches the repository. Uses a fake repository, no database.
- `tests/core/test_repositories.py` — `filter()` applied to a throwaway table declared in the test
  module: each common filter narrows, an unknown `order_by` raises.

## Done when

`uv run lint-imports` passes with the `core` layers contract active, `app.main:app` still imports at
the same path, `/v1/catalog` and `/v1/platforms/bristlecone` are byte-identical to the goldens
captured at the top of the checkpoint, and no file under `app/core/domain/` or
`app/core/application/` imports `sqlmodel`, `sqlalchemy`, or `fastapi`.
