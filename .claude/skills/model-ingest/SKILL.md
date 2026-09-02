---
name: model-ingest
description: Getting a platform's 3D build model — or a new option's geometry/finish inside it — from a modeller's GLB file into the running site. Use this whenever a platform's BuildModel framing changes, whenever an option's OptionModelEffect (nodes or material_target) is added or edited in seed/catalog.yaml, whenever someone asks to add or update a 3D model, and whenever the configurator shows a poster but never mounts the viewer for a platform that should have one. Since Stage 17 removed the 2D layer composite, the 3D build view is the only build view, and an option with geometry that never reaches a synced model is a customer-visible gap, not a cosmetic one.
---

# Model ingest

## The shape of the problem

`api/seed/catalog.yaml` is where a `BuildModel`'s camera framing and an option's `OptionModelEffect`
are declared — that half is content, versioned like everything else in the catalog. But the GLB
itself is a large binary (5–50 MB) that does not belong in git and cannot go through a normal HTTP
request: **a Vercel function caps a request body at 4.5 MB**, which is why there is no upload
endpoint and never will be. See the Stage 15 page of the
[archived development plan](https://app.notion.com/p/3ce774db73568150bcd2cb9e6b099239) in Notion.

So the model reaches the site through a second, parallel pipeline to the one `catalog-change`
describes, with its own CLI:

```
a modeller authors/edits a GLB, naming nodes and materials to match seed/catalog.yaml
        ↓  api/seed/models/<platform-slug>.glb           gitignored, operator's machine only
        ↓  app/assets.py::read_glb                        parses node + material names, no scene load
        ↓  SyncModelsUseCase.validate                      every OptionModelEffect.nodes / .material_target
                                                             must exist in the GLB, or the sync refuses
        ↓  SyncModelsUseCase.run → IBlobStore.put           content-addressed upload to Vercel Blob
        ↓  PlatformRepositoryPostgres.write_model_reference url, content_hash, byte_size onto BuildModel
        ↓  WebhookCacheInvalidator                          POST /api/revalidate, same webhook catalog-change uses
rendered /configurator/[slug]                               BuildViewer3D mounts once platform.model is non-null
```

Skipping the last three steps is the normal failure here: the catalog change looks complete because
`seed/catalog.yaml` and Postgres agree on the *framing*, but the viewer never mounts because
`platform.model` stays `null` until a model's bytes have actually been uploaded (see
`PlatformMapper._model`'s deliberate `None`-on-empty-`url` behavior).

## The node-naming contract

`docs/domain-model.md` pins the convention a modeller has to follow:
**`<platform>_<group>_<option>`**, using each entity's own slug — e.g.
`bristlecone_recovery-protection_winch-12000`. This is not enforced by any schema; it is a contract
with whoever authors the file. What *is* enforced is narrower and happens at sync time: every node
named in an option's `model_effect.nodes` and every `material_target` must exist in the GLB, or
`SyncModelsUseCase.validate` refuses the whole sync rather than uploading a model that would silently
reveal nothing for that option. A node absent from the file is not an error the application can catch
before that point — the naming convention is what makes the two sides agree in the first place.

## Working a model through

1. **Author or receive the GLB**, with node and material names following the convention above for
   every option that has a `model_effect` in `seed/catalog.yaml`. Cross-check spelling against the
   seed file — a mismatch here fails validation, not gracefully at runtime.
2. **Place it** at `api/seed/models/<platform-slug>.glb`. The filename's stem is read as the
   platform slug; it has to match one already seeded.
3. **Declare or confirm the framing** in `seed/catalog.yaml`'s `model:` block for the platform —
   `camera_orbit_deg`, `camera_distance_m`, `camera_target_y_m`. Content, not code: the right orbit
   for a 24-foot expedition truck is not the right orbit for a service body. Re-seed
   (`python -m app.seed`) if this changed.
4. **Dry-run first**:
   ```bash
   docker compose exec api python -m app.assets sync --dry-run
   ```
   This validates every `.glb` in `seed/models/` against the catalog's model effects and reports
   what would upload, writing nothing. A `ModelTooLargeError` (over `model_max_bytes`, 32 MiB
   default) or a missing node/material surfaces here, not after an upload.
5. **Sync for real**:
   ```bash
   docker compose exec api python -m app.assets sync
   ```
   Needs `BLOB_READ_WRITE_TOKEN` in the environment reaching the container; without it, `_blob_store`
   falls back to `LocalBlobStore` (fine for local iteration, not for anything meant to reach
   production). This uploads unchanged-hash files idempotently — a re-run after a no-op edit does
   not re-upload — writes `url` / `content_hash` / `byte_size` onto the platform's `BuildModelTable`
   row, and revalidates the same cache tags `cache-and-revalidation` describes, unless
   `--no-revalidate` is passed (e.g. in CI, where there is no web app to tell).
6. **Confirm the viewer actually mounts** — `curl -s localhost:8000/v1/platforms/<slug> | jq '.model'`
   should no longer be `null`, and `/configurator/<slug>` should load the 3D chunk instead of staying
   on the poster.

## When there is no GLB at all

No model file is in the repo, and none can be — so a fresh clone has `platform.model` null on
every platform, the configurator stays on its poster, and `e2e/configurator.spec.ts`'s "the 3D
canvas mounts" spec skips itself. Nothing about the 3D half is exercised, and nothing fails to
say so.

`api/tools/make_placeholder_models.py` generates a low-poly stand-in per demo platform, built to
be correct exactly where the pipeline looks: every node named by an option's `model_effect`
exists, the paint material is `body_paint`, and the geometry is sized to the camera framing
`seed/catalog.yaml` pins, so a toggle moves something inside the frame rather than off-screen.

```bash
cd api && uv run python tools/make_placeholder_models.py seed/models
```

Then walk the steps above from the dry-run onward. Output is deterministic, so re-running it and
re-syncing reports `unchanged` rather than churning a new blob. This is scaffolding for testing
the pipeline, not a substitute for the real asset: when a modeller's GLB lands, it replaces the
file of the same name and the tool goes back to being how you test the ingest chain without one.

### The Blender build

`api/tools/refine_models_blender.py` writes the same three platforms as recognisable trucks
rather than stand-ins — conventional cab, hood, raked windscreen, arched fenders, lathed tyres on
spoked rims, and a rear body per platform, matched to `web/public/images/<slug>/hero.jpg`. It
needs Blender (5.2 here) and produces 1.5–2 MB GLBs of 48–66k triangles, against the placeholder's
110–130 KB:

```bash
cd api && blender -b -P tools/refine_models_blender.py -- seed/models
```

It also runs through the Blender MCP server by `exec`-ing the file from `execute_blender_code` —
that server refuses to start in background mode, so it needs a GUI Blender or `xvfb-run -a
blender`, and the glTF exporter needs a context override the file already applies.

Two things to know before reaching for it:

- **It re-derives nothing about the contract.** `check_contract` diffs its node set against
  `make_placeholder_models`'s and exits rather than exporting a GLB the sync would refuse, so that
  file stays the one place the catalog's node names are mirrored.
- **A re-run always uploads.** Blender's glTF exporter is not byte-reproducible — two consecutive
  runs give identical-size, different-byte GLBs — so unlike the placeholder generator, rebuilding
  and re-syncing never reports `unchanged`.

## The gotcha that breaks an unrelated test

**`python -m app.assets sync` writes to the same Postgres `pytest` reads.** There is no separate test
database. `tests/modules/catalog/test_catalog_api.py` asserts a never-synced platform's `model` is
`None` — syncing a model locally, including a synthetic GLB for manual viewer testing, breaks that
test with no code change in sight until the `buildmodel` row is reverted (`url`, `content_hash` back
to `''`, `byte_size` to `0`) and anything written under `web/public/models/` is removed. CI never runs
`assets sync` at all — only `app.seed` — so every platform's `model` is `null` there too; code that
assumes a model exists needs to degrade to that state, not just to the happy path.

## Related

`catalog-change` — the parallel content chain for everything that is *not* the model's bytes; a
`model_effect` addition is a step in that chain that ends here.
`alembic-migration` — only relevant if `BuildModelTable` or `OptionModelEffectTable`'s shape changes,
not for a routine model swap.
