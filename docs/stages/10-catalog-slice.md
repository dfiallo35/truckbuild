# Stage 10 — `catalog` becomes a slice

> **Status: not started.**

**Goal:** the `catalog` module has all four layers filled in and the shims disappear. Pure pydantic
entities in `domain/`, an `IPlatformRepository` it owns, SQLModel tables and a mapper in
`infrastructure/postgres/`, use cases in `application/`, and a router that names none of it. The
N+1 goes with it.

`catalog` is the right module to migrate first: it is read-only, it has the two endpoints with a
golden diff already captured, and it is the one whose `domain/` the pricing mirror rests on. It is
also where the payoff is most visible — `_serialize_platform` is a 60-line function in an HTTP
handler that issues three queries per platform and depends on lazy-loading the ORM object graph
inside the request session. The object graph *is* the read model today.

**Prerequisite:** Stage 9 checkpoint passes.

## The target slice

```
app/modules/catalog/
├── domain/
│   ├── models.py            Platform · OptionGroup · Option · OptionRule · Asset   (pydantic)
│   ├── interfaces.py        IPlatformRepository · ICacheInvalidator
│   ├── filters.py           PlatformFilter — slug_eq · slug_in · purpose_eq
│   ├── exceptions.py        PlatformNotFoundError(404, "unknown_platform")
│   ├── enums.py             SelectionMode · DisplayStyle · RuleRelation · AssetKind   (unchanged)
│   ├── pricing.py           price_build   — still forbids sqlmodel/sqlalchemy/fastapi
│   └── rules.py             validate_selection
├── application/
│   ├── dtos.py              PlatformOutput · CatalogOutput · OptionGroupOutput · …   ← schemas.py
│   ├── mappers.py           PlatformMapper — domain → DTO
│   ├── use_cases.py         GetCatalogUseCase · GetPlatformUseCase · RevalidateCatalogUseCase
│   └── services.py          CatalogService(BaseService)
├── infrastructure/
│   ├── postgres/
│   │   ├── tables.py        PlatformTable · OptionGroupTable · OptionTable · OptionRuleTable · AssetTable
│   │   ├── mappers.py       table ↔ domain
│   │   └── repositories.py  PlatformRepositoryPostgres
│   └── webhook/
│       └── revalidate.py    ← core/revalidate.py, now implementing ICacheInvalidator
└── presentation/
    ├── catalog_api.py       ← router.py, minus every query and every mapping
    ├── filters.py           PlatformFilter (query params) with .to_domain()
    ├── dependencies.py      Depends(get_session) → repository → service
    └── routes.py            the module's router, included by main.py
```

## The two halves of every entity

This is the change that makes the layer boundary real, so it is worth spelling out once.

```python
# domain/models.py — what the business means. Pure pydantic.
class Platform(BaseEntity):
    slug: str
    name: str
    base_price_cents: int
    option_groups: list[OptionGroup] = []
    rules: list[OptionRule] = []

# infrastructure/postgres/tables.py — how it is stored. SQLModel.
class PlatformTable(BaseTable, table=True):
    __tablename__ = "platform"
    slug: str = Field(unique=True, index=True)
    ...

# infrastructure/postgres/mappers.py — the seam.
class PlatformMapper(BaseMapper):
    def to_domain(self, row: PlatformTable) -> Platform: ...
    def to_table(self, entity: Platform) -> PlatformTable: ...
```

`__tablename__` is set explicitly on every table. SQLModel derives it from the class name, so
renaming `Platform` to `PlatformTable` would silently rename five tables — which autogenerate will
happily write as `drop_table` + `create_table`, taking the data with it. Pin the names, then check
the generated revision is empty apart from the two columns Stage 9 added.

The domain `Platform` carries its option groups and rules as *loaded values*, not lazy
relationships. That is the N+1 fix stated as a type: the repository decides what a `Platform` costs
to produce, and no layer above it can accidentally trigger a query by reading an attribute.

## Steps

1. **Split the entities.** Five in `domain/models.py`, five in `infrastructure/postgres/tables.py`,
   one mapper module between them. `domain/entities/` is deleted. `tests/test_entity_registry.py`
   moves to asserting over the *tables*, which is what it was always really checking.

2. **`IPlatformRepository` in `domain/interfaces.py`**, extending `IBaseRepository`:
   `by_slug(slug)`, `slugs()`, and `all()` in the sense of "every platform, fully loaded". A port
   belongs to the module that owns the data, and `catalog` owns all of it.

3. **`PlatformRepositoryPostgres` absorbs every query in the module.** The three from
   `_serialize_platform`, the two lookups in `get_catalog` / `get_platform`, and — because they read
   catalog data and therefore belong here rather than in `quotes` — the `_platform_by_slug`,
   `_options_of` and `_rules_of` helpers currently living in the quotes router.

   **Fix the N+1 in the same move:** eager-load the group and option graph and fetch assets and
   rules in one query each, rather than three per platform. This is the one behavioural change the
   stage permits, and it is invisible on the wire — which is what the golden diff is for.

4. **The pricing shims disappear.** `PriceablePlatform`, `PriceableOption`, `RuleablePlatform`, and
   `rules.py`'s own `OptionRule` exist only because entities used to be ORM rows that
   `pricing.py` was forbidden to import. With `domain/models.py` pure, `price_build` and
   `validate_selection` take the real entities and the four shim types are deleted.

   Use the **pricing-mirror** skill for this step. Two hard guards: `fixtures/pricing-cases.json`
   must not change by a byte, and `web/src/lib/pricing.ts` and `rules.ts` must not be touched at all.
   If either moves, the shims stay and this step is dropped — it is a tidy-up, not the point of the
   stage.

5. **Use cases.** `GetCatalogUseCase(ListUseCase)` and `GetPlatformUseCase(GetByIdUseCase)`, the
   latter overriding `exec(slug)` to build `PlatformFilter(slug_eq=slug)` and raising
   `PlatformNotFoundError` rather than returning `None`. `CatalogService(BaseService)` sets
   `mapper` and `filter_class` and overrides `init_use_cases` to swap in both.

6. **`revalidate` moves into the module.** `ICacheInvalidator` in `domain/interfaces.py`,
   `core/revalidate.py` → `infrastructure/webhook/revalidate.py` implementing it, and
   `RevalidateCatalogUseCase(BaseUseCase)` in `application/use_cases.py` taking the invalidator and
   the repository (for the "no tags named → every platform tag" default). `tests/core/test_revalidate.py`
   moves to `tests/modules/catalog/`.

   Admin still owns the `POST /v1/admin/revalidate` route; in Stage 12 it calls this use case
   through `catalog`'s application facade instead of importing the adapter. `catalog` owning the
   invalidator is what `admin → catalog` means.

7. **The router keeps exactly three things:** the ETag / `Cache-Control` / 304 handling, the
   `PlatformNotFoundError` → 404 rendering (via the handler, not an `HTTPException`), and the call
   into the service. `_etag_for` and `_cached_response` are HTTP cache-protocol code and stay in
   presentation. Everything else leaves.

8. **Contracts.** Two new ones, both written with `containers` so a fourth module inherits them the
   day it is created:

   - **`Domain forbids persistence`** — every module's `domain` (and `app.core.domain`) forbids
     `sqlmodel` and `sqlalchemy`. This is the whole migration restated as a rule CI enforces, and
     it is the reason the entity split was worth doing. It can only be turned on for `catalog`
     this stage; scope it to `app.modules.catalog.domain` and `app.core.domain` now, widen it in
     Stages 11 and 12.
   - **`Presentation forbids persistence`** — every module's `presentation` forbids `sqlmodel` and
     `sqlalchemy`. Same widening schedule.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

grep -rn "sqlmodel\|sqlalchemy" app/modules/catalog/domain/ app/modules/catalog/presentation/
# no hits

git diff --stat fixtures/pricing-cases.json web/src/lib/pricing.ts web/src/lib/rules.ts
# empty

curl -s localhost:8000/v1/catalog               | jq -S . | diff tests/golden/catalog.json -
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . | diff tests/golden/platform-bristlecone.json -
```

The N+1 fix needs a check that survives the next refactor, so assert it rather than eyeballing a
log. Add `tests/modules/catalog/test_catalog_queries.py`, counting statements with a SQLAlchemy
`before_cursor_execute` listener on `engine`, and seed a fourth platform inside the test: the count
must not move.

```python
count = 0

@event.listens_for(engine, "before_cursor_execute")
def _count(*_args, **_kwargs):
    nonlocal count
    count += 1
```

Then, because the catalog is what every marketing page renders from:

```bash
cd ../web && pnpm test && pnpm build      # must still print "- Cache Components enabled"
```

## Done when

`app/modules/catalog/domain/` imports no ORM and `presentation/` names no query, `GET /v1/catalog`
issues a constant number of statements regardless of how many platforms are seeded, both golden
diffs are empty, and `fixtures/pricing-cases.json` is unchanged.
