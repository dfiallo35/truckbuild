# Stage 1 — Backend: catalog, pricing, and rules

**Goal:** the catalog exists in Postgres, is served over HTTP, and can be priced and validated by pure,
well-tested functions.

**Prerequisite:** Stage 0 checkpoint passes.

## Steps

1. **SQLModel tables** in `app/models/` — `Platform`, `OptionGroup`, `Option`, `OptionRule`, `Asset`.
   Slugs are the public identifiers; give them unique constraints.
2. **Initial Alembic migration** — generated, then read before committing. Autogenerate gets enums and
   constraints wrong often enough that reviewing the output is not optional.
3. **`seed/catalog.yaml`** — the three placeholder platforms from
   [domain-model.md](../domain-model.md), including the compatibility rules listed there.
4. **`app/seed.py`** — loads the YAML idempotently, upserting by slug so re-seeding is always safe.
5. **`services/pricing.py`** and **`services/rules.py`** — pure functions with **no DB and no FastAPI
   imports**:
   - `price_build(platform, selected_option_slugs) -> PriceBreakdown`
   - `validate_selection(platform, selected_option_slugs) -> list[RuleViolation]`

   Isolating them this way is what makes them cheap to test and safe to mirror on the client. Write these
   test-first.
6. **`routers/catalog.py`**
   - `GET /v1/catalog` — every platform with nested groups, options, and rules. One round trip; the catalog
     is small enough that splitting it costs more than it saves.
   - `GET /v1/platforms/{slug}` — one platform, same nested shape.
   - Both send `ETag` and `Cache-Control`.

## Checkpoint

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
curl -s localhost:8000/v1/catalog | jq '.platforms[].slug'
# "bristlecone" "ironwood" "sentinel"
docker compose exec api python -m app.seed   # re-run: no duplicates
docker compose exec api pytest -q
```

## Done when

- Every `requires`/`excludes` rule in the seed has a passing test, both for the satisfied and violated case.
- Re-seeding twice leaves the row counts unchanged.
- `pricing.py` and `rules.py` import nothing from `fastapi` or `sqlmodel`.
