# Stage 12 — `admin` becomes a slice, and the filter convention earns its keep

> **Status: not started.**

**Goal:** `admin` stops reaching into other modules' internals. Its three endpoints call use cases;
its 64-line query composition becomes a `QuoteFilter` and a repository override; and it renders
leads through its own DTOs rather than borrowing `quotes`' wire schema.

`admin` owns no tables and no repository — it has an `application/` and a `presentation/` and
nothing else. Its use cases are thin, but they exist, because the alternative is an admin router
calling two other modules' repositories directly, which is exactly the coupling this migration
removes.

**Prerequisite:** Stage 11 checkpoint passes.

## The target slice

```
app/modules/admin/
├── application/
│   ├── dtos.py              QuoteSummaryOutput · QuotePageOutput · QuoteDetailOutput
│   │                        RevalidateRequest · RevalidateOutput
│   ├── mappers.py           quotes.domain.Quote → admin's own DTOs
│   └── use_cases.py         ListQuotesUseCase · GetQuoteUseCase · RevalidateCatalogUseCase (delegating)
└── presentation/
    ├── admin_api.py         ← router.py, minus the query composition
    ├── filters.py           AdminQuoteFilter (query params) — where MAX_PAGE_SIZE lives
    ├── dependencies.py      require_admin, and the two repositories it consumes
    └── routes.py
```

## Steps

1. **The query composition becomes a filter.** `list_quotes` currently builds `conditions` inline,
   escapes `ILIKE` wildcards, runs a count, runs a grouped line-count subquery, and paginates —
   inside one HTTP handler. All of it moves:

   - `kind`, `platform_slug`, `q` become `kind_eq`, `platform_slug_eq`, `search` on
     `quotes.domain.filters.QuoteFilter`, following the `_eq` / `_in` / `_ilike` convention from
     Stage 9. The filter is `quotes`' because the data is `quotes`'.
   - `_escape_like` and the `or_(...)` across `ref` / `contact_name` / `contact_email` move into
     `QuoteRepositoryPostgres.filter()`, which calls `super().filter(...)` first and then chains its
     own `.where(...)` — the reference's pattern exactly.
   - The pagination *policy* goes with it: `created_at DESC, id DESC` ordering (the `id` tiebreak
     matters — two leads can share a `created_at` to the microsecond under a test clock, and a
     wobbling page boundary drops or repeats a lead) and the one-count-per-page line subquery are
     decisions about how leads are read.

   **`MAX_PAGE_SIZE` stays in `presentation/filters.py`**, as `Query(ge=1, le=100)`. A bound on a
   query parameter is an HTTP concern and belongs where FastAPI can reject it with a 422 before
   anything else runs. This is the case `core/presentation/filters.py` was built for.

2. **Three use cases.** `ListQuotesUseCase(PaginateUseCase)` over `IQuoteRepository`;
   `GetQuoteUseCase(GetByIdUseCase)` overriding `exec(ref)` to build `QuoteFilter(ref_eq=ref)`;
   and `RevalidateCatalogUseCase` delegating to the one `catalog` owns since Stage 10. `admin`
   consumes `quotes.domain.interfaces.IQuoteRepository` and `catalog`'s application facade — it
   defines neither, which is what `admin → quotes → catalog` means in practice.

3. **`admin` gets its own output DTOs.** The router imports `QuoteDetail` from
   `quotes/presentation/schemas.py` today — the last facade violation in `pyproject.toml`, and a
   real one: a staff-facing lead view and a customer-facing submission response are two audiences
   whose fields will diverge the first time either changes. `admin/application/mappers.py` maps
   `quotes.domain.Quote` to admin's own shapes.

   The **wire bodies must not change** in this stage. `QuoteSummary`, `QuotePage` and the detail
   body keep their field names, types, and ordering; `web/src/app/(site)/admin/` is not touched.
   Diverging the two audiences is now *possible* — doing it is a product decision for another day.

4. **`require_admin` stays on the router.** The bearer-token guard is HTTP authentication, and it
   is declared as a router-level dependency so a route added later is guarded by construction rather
   than by the author remembering. `secrets.compare_digest` stays — a long-lived shared token is
   exactly the kind worth guessing at.

5. **Land the full contract set**, replacing the piecemeal ones from Stages 10 and 11. Applied with
   `containers` across every module, and with `app.core` carrying the same rules:

   ```
   Layers within every module     presentation | infrastructure  →  application  →  domain
   Layers within core             (the same, over app.core)
   Module direction               admin → quotes → catalog → core
   Facade of catalog              quotes, admin ⊘ catalog.presentation, catalog.infrastructure
   Facade of quotes               admin       ⊘ quotes.presentation, quotes.infrastructure
   Domain forbids persistence     every domain ⊘ sqlmodel, sqlalchemy
   Domain isolation               every domain ⊘ fastapi, starlette, httpx
   Presentation forbids persistence   every presentation ⊘ sqlmodel, sqlalchemy
   Pricing mirror purity          pricing, rules ⊘ sqlmodel, sqlalchemy, fastapi
   ```

   `main.py`, `core/presentation/app.py`, and each module's `presentation/dependencies.py` are the
   composition root and are declared as such — the only places allowed to see across a layer
   boundary, because something has to know how the pieces are assembled.

   **`ignore_imports` must be empty.** Every exception the migration inherited has a stage that
   removed it; if one is still there, that stage is not finished.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                        # full contract set, no ignore_imports
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

grep -rn "ignore_imports" pyproject.toml
# no hits

grep -rn "select(\|session\.\|Session" app/modules/*/presentation/
# no hits
```

The admin list is the one endpoint with no golden file, because its body depends on submitted
leads. Capture one instead, against a seeded fixture set, before and after:

```bash
TOKEN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $TOKEN" \
  'localhost:8000/v1/admin/quotes?limit=5&kind=build&q=bristlecone' \
  | jq -S 'del(.items[].created_at)' | diff /tmp/admin.before.json -
```

Plus the pagination edge that the `id` tiebreak exists for: submit three leads inside one test,
read them back as three pages of one, and assert no `ref` is missing or repeated.

## Done when

`pyproject.toml` has no `ignore_imports`, the full contract set passes, no module's `presentation/`
names a persistence type, `admin` imports nothing from another module's `presentation` or
`infrastructure`, and the admin page in `web/` renders unchanged against the running API.
