# Stage 17 — retire the 2D composite

> **Status: not started.**

**Goal:** the layered-image viewer and everything that fed it come out — content, columns, DTOs, Zod
schemas and the enum value — leaving the 3D viewer as the only build view, and the docs telling the
truth about it.

**Prerequisite:** Stage 16 checkpoint passes, and every platform in `seed/catalog.yaml` has a synced
model. This stage is what makes the 3D viewer load-bearing, so it should not land the same day as
the stage that introduced it — give the viewer a deployment's worth of real use first.

## What comes out

`Platform.viewer_base`, `Option.layer`, `LayerOutput`, `layerSchema`, `AssetKind.layer`, every
`layer:` and `viewer_base:` block in `seed/catalog.yaml`, and `web/public/images/*/viewer/`.

**`swatch` stays.** The finish chips in the option panel are 2D thumbnails and are still exactly
right; only the full-body layer renders they sat beside are going.

## Steps

1. **Content first** — strip `layer:` and `viewer_base:` from `api/seed/catalog.yaml`; delete
   `web/public/images/*/viewer/`.

2. **Backend** — remove the fields and the enum value across `domain/models.py`, `domain/enums.py`,
   `application/dtos.py`, `application/mappers.py` (including the `_layer` helper and the
   `sort_order` → `z_index` translation its docstring explains),
   `infrastructure/postgres/mappers.py` and `infrastructure/postgres/repositories.py`
   (`_upsert_platform_assets`' viewer-base branch and `_upsert_option_assets`' layer branch).

3. **The dangerous migration.** `AssetKind` is stored as a **native Postgres enum type**
   (`assetkind`), and Postgres cannot drop a value from one. The migration must:

   1. `DELETE FROM asset WHERE kind = 'layer'`
   2. create a new enum type with the three remaining values
   3. `ALTER TABLE asset ALTER COLUMN kind TYPE … USING kind::text::…`
   4. drop the old type

   **Autogenerate will not produce this and will not warn that it hasn't** — it will emit an empty
   migration and look successful. Write it by hand, use the `alembic-migration` skill, and test
   `upgrade` *and* `downgrade` against a seeded local database before committing. The downgrade has
   to recreate the value; it cannot recreate the deleted rows, and the migration should say so in a
   comment rather than pretend otherwise.

4. **Web** — remove `layerSchema` and the `layer` / `viewer_base` fields from
   `web/src/lib/contract.ts`, and delete the composite code paths still sitting in
   `BuildViewer.tsx` after Stage 16.

5. **Golden recapture**, in the same commit as the `catalog.yaml` edit. This diff is subtractive and
   is the one worth reading line by line.

6. **Docs**, which are load-bearing in this repository:

   - `docs/decisions.md` — move "a 3D/WebGL viewer" out of **Explicitly deferred**. Record what
     replaced it: the reference-in-Postgres / bytes-in-Blob split, the content-addressed path, the
     4.5 MB function-body limit that ruled out an upload endpoint, and the no-WebGL accepted risk
     under **Accepted risks** where it belongs.
   - `docs/PLAN.md` — mark stages 14–17 complete.
   - `docs/stages/04-configurator.md` — its "most of the perceived value of 3D at a fraction of the
     cost" claim is now history. Annotate it as such; do not delete it. It was true when written and
     the reasoning is worth keeping.
   - `docs/domain-model.md` — `BuildModel`, `OptionModelEffect`, and the GLB node-naming convention
     a modeller has to follow, which is now a contract with whoever authors the files.
   - `docs/architecture.md` and `CLAUDE.md` — `IBlobStore` in the kernel's layer list; the fixed
     catalog query count at its new number; `python -m app.assets` beside `python -m app.seed`; the
     configurator viewer described as WebGL rather than as a layer composite.
   - `.claude/skills/catalog-change/SKILL.md` — the chain now ends in a model sync. An option with
     geometry that is added without one is a half-finished catalog change, which is the exact
     failure that skill exists to prevent.
   - **A new `.claude/skills/model-ingest/`** — author → validate → upload → revalidate. This is the
     cross-service, easy-to-leave-half-done shape the project skills are for, and after this stage
     it is the second such chain in the repo.

## Checkpoint

The full CI-equivalent sweep, via the `stage-checkpoint` skill:

```bash
cd api
uv run ruff format --check . && uv run ruff check . && uv run lint-imports && uv run pytest
uv run alembic downgrade -1 && uv run alembic upgrade head   # round-trips cleanly

cd ../web
pnpm format:check && pnpm lint && pnpm test && pnpm build && pnpm bundle:check && pnpm e2e
```

```bash
grep -rn "viewer_base\|AssetKind.layer\|layerSchema" api/app web/src
# no hits
```

## Done when

No occurrence of `viewer_base`, `AssetKind.layer` or `layerSchema` remains outside `alembic/versions/`
and the stage docs, the migration round-trips, the full sweep is green, and `docs/decisions.md` no
longer lists a 3D viewer as deferred work.
