---
name: catalog-change
description: Walks a TruckBuild catalog change all the way through both services — adding or editing a platform, option group, option, price, image, spec, or compatibility rule — so nothing is left half-wired. Use this whenever seed/catalog.yaml or anything under api/app/modules/catalog/ changes, whenever someone asks to add a new truck platform or option, reprice something, rename a slug, or add a field to the catalog, and whenever catalog data appears correct in Postgres but wrong or stale on the site. The chain from YAML to a rendered page crosses seven files in two services and a cache boundary, so partial changes are the normal failure here.
---

# Changing the catalog

## The shape of the problem

The catalog is defined once in YAML but observed in six more places before a visitor sees it. A change
that stops halfway shows up as a field that is present in Postgres and absent on the page, or a Zod
error nobody sees because the page is still serving from cache.

Since stage 8 the API half of that chain is a walk **down one module** rather than across four
directories — `api/app/modules/catalog/`, one layer at a time:

```
api/seed/catalog.yaml                    source content, version controlled
        ↓  catalog/infrastructure/catalog_file.py       YAML read
        ↓  catalog/application/use_cases.py::SeedCatalogUseCase   upsert by slug
                                          (app/seed.py is the thin CLI over this)
Postgres                                 runtime source of truth
        ↓  catalog/infrastructure/postgres/tables.py    SQLModel tables (+ migration if shape changed)
        ↓  catalog/infrastructure/postgres/mappers.py   table → domain entity
        ↓  catalog/domain/models.py                     the pure entity
        ↓  catalog/application/mappers.py               domain → DTO
        ↓  catalog/application/dtos.py                  the response shape
        ↓  catalog/presentation/catalog_api.py          GET /v1/catalog, GET /v1/platforms/{slug}
web/src/lib/contract.ts                  Zod schemas at the boundary
        ↓  'use cache' + cacheTag('catalog') / cacheTag('platform-<slug>')
        ↓  catalog/infrastructure/webhook/revalidate.py → POST /api/revalidate → revalidateTag
rendered page
```

Since stage 10 a new field crosses **two mappers, not none**: the table → domain one in
`infrastructure/postgres/mappers.py` and the domain → DTO one in `application/mappers.py`. Missing
either is the new common half-finish — the column exists, the entity carries it, and the response
does not.

Everything above lives under one directory. `app/seed.py` sits outside it on purpose: it's the
composition root's second CLI entrypoint, and it's the only thing in this chain allowed to build
an adapter directly rather than receive one through `Depends`.

## Locating the chain

This repo is indexed by CodeGraph (`.codegraph/` at the root, spanning both services). One query
returns the verbatim source of every link in the chain above plus who calls what, which is faster and
less lossy than grepping for a field name across `api/` and `web/` separately:

```bash
codegraph explore "how does a platform go from catalog.yaml through the router to the rendered page"
codegraph explore "OptionGroup"      # model, schema, Zod parse, and the components that render it
```

The blast-radius section of that output is the practical answer to "what else does this field touch" —
use it to check nothing in the seven-step list below got skipped. Fall back to grep only for things
that are not symbols, such as a YAML key or a slug string.

## Two kinds of change

Work out which one you have before touching anything — they need different amounts of the chain.

**Content change** — a new option, a different price, a new rule, a swapped photo. The shape is
unchanged, so: edit `seed/catalog.yaml`, re-seed, revalidate the affected tags. No migration, no Zod
change. If it touches a price or a rule, it also touches the pricing mirror — see below.

**Shape change** — a new field, a new entity, a changed relation. This walks the whole chain:
model → migration → seed loader → Pydantic schema → router → Zod schema → the component that renders
it. Skipping the Zod schema is the common miss; the parse then silently drops the field and the
component renders `undefined` with no error.

## Working a change through

1. **`api/seed/catalog.yaml`** — the content lives here, not in a migration and not typed into psql.
   Committing it is what keeps catalog content reviewable in diffs.
2. **`api/app/modules/catalog/infrastructure/postgres/tables.py`** — shape changes only. Slugs
   carry unique constraints, and `__tablename__` is pinned on every table (SQLModel would otherwise
   derive it from the class name, and renaming a class renames a table). A new table must be reached
   by `alembic/env.py`'s import, or autogenerate never sees it; `tests/test_entity_registry.py`
   fails if you forget.

   Then **`domain/models.py`** if the field is part of what a platform *means*, and
   **`infrastructure/postgres/mappers.py`** to carry it across.
3. **Alembic migration** — shape changes only. Generate it, then *read it* before committing; see the
   `alembic-migration` skill for why autogenerate output is not trustworthy unreviewed.
4. **`api/app/modules/catalog/infrastructure/postgres/repositories.py`**'s
   `upsert_from_catalog` — upserts by slug so re-seeding is always safe. If you added a field,
   the upsert has to carry it, or re-seeding will quietly leave existing rows on the old value.
   `app/seed.py` is a thin CLI over this; it needs no change for a content or field addition.
5. **`api/app/modules/catalog/application/`** — `dtos.py` for the response shape, then
   `mappers.py` to fill it from the entity. The nested platform → groups → options → rules shape
   goes out in one round trip; the catalog is small, and splitting it costs more than it saves.
   `presentation/` needs no change for a new field — it only does ETags and the service call.

   If the new data needs another *query*, it belongs in
   `infrastructure/postgres/repositories.py`, added to the fixed set of statements
   `_rows_for` already issues rather than as a lookup per platform.
   `tests/modules/catalog/test_catalog_queries.py` fails if the count moves.
6. **`web/src/lib/contract.ts`** — extend the Zod schema. Parsing rather than casting at this boundary is
   what turns a backend shape change into a clear named-field error instead of a runtime `undefined`
   several components deep.
7. **Cache tags and revalidation** — the change is invisible until the right tag is revalidated. See
   the `cache-and-revalidation` skill.
8. **Pricing mirror** — if a price, a delta, or a `requires`/`excludes` rule changed, the shared
   fixture and both implementations need updating. See the `pricing-mirror` skill.

## Verifying

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
curl -s localhost:8000/v1/catalog | jq '.platforms[].slug'
docker compose exec api python -m app.seed    # re-run: row counts must not change
```

Re-seeding twice and getting identical row counts is the real test of the upsert. Then reload the
public page and confirm the change actually surfaced — if Postgres is right and the page is not, the
problem is a cache tag, not the catalog.

## Renaming a slug is a breaking change

Slugs are the public identifiers. They appear in `/builds/<slug>`, `/configurator/<slug>`,
`?o=slug-a,slug-b` build URLs that customers have already shared, the pricing fixtures, and the
`platform-<slug>` cache tags. Renaming one silently breaks every shared build that referenced it.

If a rename is genuinely needed, treat it as a migration with a redirect, not an edit: keep the old
slug resolving, and update the fixtures and cache tags in the same change.

## Domain vocabulary

`docs/domain-model.md` is the authority. Briefly: a **Platform** is a configurable product line; an
**OptionGroup** is one configurator step with a selection mode and display style; an **Option** is a
choice with a price delta and an optional layer image for the viewer; an **OptionRule** is a
`requires` or `excludes` relation between options; a **Build** is a platform plus selected slugs; a
**Quote** is a submitted build plus contact details.

Getting this vocabulary right once is what keeps the two services agreeing. The three placeholder
platforms (Bristlecone, Ironwood, Sentinel) and their prices are demo content awaiting real data.
