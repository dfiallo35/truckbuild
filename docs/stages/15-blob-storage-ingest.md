# Stage 15 — blob storage, and the ingest CLI

> **Status: not started.**

**Goal:** the model files reach Vercel Blob and their references reach Postgres, through one command
run by an operator — `python -m app.assets sync` — with every node and material name in
`seed/catalog.yaml` validated against what the GLB actually contains before a single row is written.

**Prerequisite:** Stage 14 checkpoint passes. That stage created the rows this one fills in.

## Why a CLI and not an upload endpoint

**A Vercel function caps request bodies at 4.5 MB.** GLB truck models run 5–50 MB. A multipart
`POST /v1/admin/assets` would work locally, work in Docker, pass every test, and fail in production
on the first real model — the worst possible failure shape.

The CLI removes the problem rather than working around it: it runs on an operator machine and PUTs
straight to `blob.vercel-storage.com`, so no Vercel function is anywhere in the byte path. It also
matches how this repository already operates — `alembic upgrade head` and `python -m app.seed` are
both run by hand from a machine with the direct Neon URL (`docs/deploy.md`), and a model sync is the
same kind of act.

It also avoids making `admin` a writer. `admin/presentation/admin_api.py`'s docstring names that as
the point at which a single shared bearer token stops being adequate; there is no reason to reach it
for a job a CLI does better.

## Why `IBlobStore` is in `core` and not `catalog`

CLAUDE.md's rule: *a thing belongs in `core` only if more than one module uses it **or** it names no
module's vocabulary.* Blob storage names no module's vocabulary — it is `put`, `delete`, `exists`
over bytes. It sits beside `IRateLimiter` as a kernel port with an infrastructure adapter, which is a
shape the kernel already has.

```
app/core/
├── domain/interfaces.py          + IBlobStore, StoredBlob
└── infrastructure/blob/
    ├── vercel.py                 VercelBlobStore  — httpx, BLOB_READ_WRITE_TOKEN
    └── local.py                  LocalBlobStore   — writes web/public/models/
app/modules/catalog/
├── infrastructure/glb.py         + node and material names out of a .glb, stdlib only
└── application/use_cases.py      + SyncModelsUseCase
app/assets.py                     the argparse shell, beside app/seed.py
```

## Steps

1. **The port** — `core/domain/interfaces.py`: `IBlobStore` with `put(path, data, content_type) ->
   StoredBlob`, `delete(path)`, `exists(path)`. `StoredBlob` is a pure value (`url`, `path`,
   `byte_size`). Pure pydantic and no `httpx` — `core/domain` may not name a transport.

2. **Two adapters**, in a new `core/infrastructure/blob/`:

   - `VercelBlobStore` — `httpx` against `https://blob.vercel-storage.com/<path>` with
     `Authorization: Bearer $BLOB_READ_WRITE_TOKEN`. Sets `cache-control: public, max-age=31536000,
     immutable`, **which is only safe because paths are content-addressed** (step 6).
   - `LocalBlobStore` — writes under `web/public/models/` and returns `/models/…`. Selected when
     `BLOB_READ_WRITE_TOKEN` is unset, so `docker compose`, CI and the tests need no credential.
     That is the same "works without the cloud" property `tests/modules/quotes/test_submit_quote.py`
     already has, and it is what makes step 7's tests real tests rather than mocks.

   The kernel's own layer contract already covers this directory; no new import-linter contract is
   needed, and none should be added.

3. **Config** — `core/config.py`: `blob_read_write_token: str | None = None`, `blob_path_prefix: str
   = "models"`, `model_max_bytes: int = 33_554_432` (32 MiB). Every env var is declared here or it
   fails at startup; that rule is why this is a numbered step and not an afterthought.

4. **The GLB reader** — `catalog/infrastructure/glb.py`. A GLB is a 12-byte header followed by
   chunks, the first of which is the glTF JSON. Reading `nodes[].name` and `materials[].name` out of
   it is ~40 lines of `struct` and `json` and **needs no new dependency**. Validate the `glTF` magic
   and the version while you are in there.

5. **The validation that makes this stage worth building.** Before writing anything, the sync
   cross-checks every `nodes:` entry and every `material_target:` in the catalog against the names
   the GLB really contains, and **refuses the whole sync** on a mismatch, naming the option, the
   missing name and the file.

   Without it, a node renamed in Blender means an option that still prices, still appears in the
   build sheet, still shows as selected — and does nothing on screen. No test would fail. This is
   the 3D equivalent of the `uq_option_rule` constraint: a content mistake caught by construction
   rather than by someone noticing.

6. **`SyncModelsUseCase`** in `catalog/application/use_cases.py`, with `app/assets.py` as the thin
   argparse shell over it, modelled on `app/seed.py` — adapters built directly, because there is no
   request to hang a `Depends` off.

   - Reads `api/seed/models/<platform-slug>.glb`. **Gitignored** — these are large binaries, and
     `seed/catalog.yaml` stays the reviewable text half of the seed.
   - sha256 each file; **skip when the hash matches the row already in Postgres.** A second run
     uploads nothing and writes nothing.
   - Refuse a file over `model_max_bytes`, and refuse one whose magic bytes are not `glTF`.
   - Upload to `<blob_path_prefix>/<platform-slug>/<sha256[:16]>.glb`. Content-addressed, so the URL
     changes when and only when the bytes do — which is what makes both the `immutable` cache header
     and the skip-on-unchanged correct rather than merely convenient.
   - Write `url` / `content_hash` / `byte_size` through `IPlatformRepository`, not by inline table
     access.
   - Revalidate `catalog` and `platform-<slug>` through the existing `WebhookCacheInvalidator`, with
     the same `--no-revalidate` opt-out `app/seed.py` has, for the same reason: a stale public page
     is the costlier mistake, so it is opt-out rather than opt-in.
   - `--dry-run` reports what would upload and writes nothing.

7. **Tests** — `tests/modules/catalog/test_model_sync.py`, against `LocalBlobStore` with a tiny
   hand-built GLB fixture (a header plus a JSON chunk naming three nodes and one material is enough;
   it needs no geometry). Assert:

   - a first sync uploads and writes the reference;
   - a second sync uploads nothing and writes nothing;
   - a file over the size cap is refused;
   - a file without the `glTF` magic is refused;
   - **a catalog naming a node the GLB does not contain fails the sync, and no row is written** —
     the one that justifies the stage.

8. **Docs** — `docs/deploy.md` gains a Blob section (create the store, set `BLOB_READ_WRITE_TOKEN`
   on the API project) and a line under "Routine deploys, afterwards": a model change is a CLI run
   from an operator machine, alongside the seed and the migration.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run lint-imports && uv run pytest

uv run python -m app.assets sync --dry-run       # reports, writes nothing
uv run python -m app.assets sync                 # LocalBlobStore, no token needed
curl -s localhost:8000/v1/platforms/bristlecone | jq '.model'
uv run python -m app.assets sync                 # "unchanged", zero uploads

# and against the real store
BLOB_READ_WRITE_TOKEN=… uv run python -m app.assets sync
```

Then break it on purpose: rename a node in `seed/catalog.yaml` to something the GLB does not
contain, run `sync`, and confirm it refuses by name and writes nothing.

## Done when

A real GLB is in Blob, its URL is in Postgres and non-null on the wire, a second `sync` is a no-op,
a deliberately wrong node name fails the sync with a message naming the node and the file, and the
whole suite passes with `BLOB_READ_WRITE_TOKEN` unset.
