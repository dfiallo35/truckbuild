# Stage 14 — the catalog carries a 3D model

> **Status: complete.** Checkpoint verified 2026-08-29.

**Goal:** the catalog gains the two entities a 3D build view needs — a `BuildModel` per platform and
an `OptionModelEffect` per option that changes something visually — through the whole chain, from
`seed/catalog.yaml` to a Zod-parsed field in the browser.

**Purely additive.** `viewer_base`, `Option.layer` and `AssetKind.layer` all stay; the 2D composite
keeps rendering and the site is untouched. Nothing in `web/` reads the new fields yet. That is what
makes this stage independently reviewable and independently revertable — the removal is
[Stage 17](17-retire-2d-composite.md), deliberately last.

**Prerequisite:** Stage 13 checkpoint passes.

## Why two mechanisms and not one

`seed/catalog.yaml` has two visually different kinds of option and one mechanism cannot serve both:

- **Geometry** — `cab-crew`, `shell-extended`, `winch-12000`, `rooftop-tent`. Selecting one should
  reveal a mesh that is already in the file. That is `nodes`.
- **Finish** — `finish-satin-black`, `finish-desert-tan`, `finish-forest-green`, the `swatch` group.
  Node visibility cannot express these: one body mesh per colour would multiply the GLB by the
  number of finishes. That is `material_target` plus a colour.

So `OptionModelEffect` carries both, and an option may use either, both, or — like `cab-regular`,
which *is* the base model — neither, exactly as it carries no `layer` image today.

## The two entities

**`BuildModel`**, one per platform:

| Field | Why |
|---|---|
| `url` | Blob URL. Empty until Stage 15's sync has run — the bytes are a large binary and do not live in the YAML. |
| `content_hash` | sha256 of those bytes. What makes a re-sync free, and what lets the blob path be content-addressed. |
| `byte_size` | So the size of what a phone downloads is visible in the database rather than only in a network tab. |
| `alt_text` | The base of the viewer's `role="img"` description. |
| `camera_orbit_deg`, `camera_distance_m`, `camera_target_y_m` | Framing. Content, not code: the right orbit for a 24-foot expedition truck is not the right orbit for a service body, and neither is a fact about the viewer. |

**`OptionModelEffect`**, at most one per option: `nodes: list[str]`, `material_target: str | None`,
`base_color_hex`, `metalness`, `roughness`.

## Steps

1. **`domain/models.py`** — `BuildModel` and `OptionModelEffect` as pure pydantic `BaseEntity`
   subclasses; `Platform.model: BuildModel | None`, `Option.model_effect: OptionModelEffect | None`.
   No ORM import; the `Domain forbids persistence` contract already checks this.

2. **`infrastructure/postgres/tables.py`** — `BuildModelTable` (`__tablename__ = "buildmodel"`,
   `platform_id` FK **unique**) and `OptionModelEffectTable` (`__tablename__ =
   "optionmodeleffect"`, `option_id` FK **unique**). **Pin `__tablename__` on both**, per the file's
   own warning.

   `nodes` is `Field(default_factory=list, sa_column=Column(JSON))` — an ordered list of opaque
   strings read and written whole, never queried into and never joined against, which is the same
   reasoning that put `PlatformTable.spec_highlights` in a JSON column.

   Both unique constraints matter: they are what stops a botched sync from leaving two rows for the
   mapper to pick between arbitrarily.

3. **Migration** — via the `alembic-migration` skill. Two `create_table`s, no enum change (that is
   Stage 17's, and it is the dangerous one). Read the generated file: check the JSON column, the
   unique FKs, and that `tests/test_entity_registry.py` sees both new tables.

4. **`infrastructure/postgres/mappers.py`** — two new buckets on `CatalogRows`
   (`model_by_platform: dict[int, BuildModelTable]`, `effect_by_option: dict[int,
   OptionModelEffectTable]`), and `_model` / `_model_effect` helpers alongside `_asset`. The mapper
   must stay session-free; that is what makes the N+1 fix structural rather than a habit.

5. **`infrastructure/postgres/repositories.py`** — two more statements in `_rows_for`: models by
   `platform_id in …`, effects by `option_id in …`. **The fixed statement count moves 5 → 7.**
   Update the module docstring and `tests/modules/catalog/test_catalog_queries.py` — the test's
   value is that the number is *fixed*, not that it is five, so rename
   `test_reading_the_catalog_is_five_statements` accordingly rather than loosening the assertion.

6. **The seed write** — `_upsert_platform_model` and `_upsert_option_model_effect` on the
   repository, following `_upsert_platform_assets` / `_upsert_option_assets` exactly, **including
   deleting a row that falls out of the YAML**. The upsert must not touch `url`, `content_hash` or
   `byte_size`: those are Stage 15's to write, and a re-seed that blanked them would silently
   un-publish every model.

7. **`application/dtos.py` and `application/mappers.py`** — `BuildModelOutput`,
   `OptionModelEffectOutput`; `PlatformOutput.model`, `OptionOutput.model_effect`.

   `content_hash` and `byte_size` are **operational, not wire** — the mapper spends them, the way
   `Asset.sort_order` already is.

   **A model with no `url` maps to `None`.** From a consumer's point of view a model whose bytes are
   not uploaded is not a model, and emitting `{"url": ""}` would force every reader to check for an
   empty string — the exact class of bug the Zod boundary exists to prevent. This means the new
   field is `null` on the wire for the whole of this stage, which is correct.

8. **`api/seed/catalog.yaml`** — a `model:` block per platform (`alt_text` and the three camera
   fields; no URL) and a `model_effect:` block on every option that has a `layer:` today. The
   existing `layer:` and `viewer_base:` blocks stay.

   Node names are a **content convention** and want writing down in `docs/domain-model.md` in this
   stage, not the next: `<platform>_<group>_<option>` is enough, and whatever is chosen becomes a
   contract with whoever authors the GLB.

9. **`web/src/lib/contract.ts`** — `buildModelSchema` and `optionModelEffectSchema`, added to
   `platformSchema` / `optionSchema` as nullable. Nothing renders them yet; an unparsed new field is
   exactly what this boundary exists to catch.

10. **Golden recapture** — `api/tests/golden/*.json`, in the same commit as the `catalog.yaml` edit,
    per `api/tests/golden/README.md`. The diff is additive and is the review.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                       # no new contract, no ignore_imports
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run python -m app.seed --no-revalidate  # re-run: row counts must not move
uv run pytest

curl -s localhost:8000/v1/platforms/bristlecone \
  | jq '{model, effect: .option_groups[0].options[1].model_effect}'
# model: null (no url yet), effect: {"nodes": ["…"], …}

cd ../web && pnpm lint && pnpm test && pnpm build
```

## Done when

`model` and `model_effect` are on the wire and parsed by Zod, `lint-imports` is green with
`ignore_imports` still empty, the query-count test passes at its new fixed number, re-seeding twice
leaves row counts unmoved, and `/configurator/bristlecone` renders the 2D composite exactly as
before.
