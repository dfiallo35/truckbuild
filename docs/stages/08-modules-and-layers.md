# Stage 8 — Modules and layers, no behaviour change

> **Status: complete.**

**Goal:** `api/app/` is a set of feature modules, each carrying its own four layers over a shared
`core`, assembled into one FastAPI app at one composition root. The layer rule, the module direction,
and the facade rule are all checked by CI, and the API's behaviour is byte-for-byte what it was
before.

Stages 0–7 built a working service. They also let the routers become the application:
`app/routers/quotes.py:205` is one function that guards for spam, queries Postgres, validates a
selection, prices a build, constructs an aggregate, commits, sends mail, and shapes a response.
There is no repository, no use case, and no port anywhere in `api/app/` — a grep for
`repository|unit_of_work|use_case|Protocol|ABC` returns nothing but `collections.abc`.

The current directories group by *kind* — all the models together, all the routers together, all the
services together. That is why adding a field to the catalog touches seven files in four
directories, and why `app/services/` ended up holding three unrelated things at once: pure domain
policy, a stateful in-process control, and outbound adapters. Grouping by **feature** puts the
catalog's entities, rules, queries, and routes next to each other, and makes the layer boundary a
rule *inside* each module rather than a directory you can wander out of.

This stage does none of the untangling. It **only moves files**, because a refactor that moves code
and changes it in the same commit cannot be reviewed: nobody can tell which hunk was mechanical and
which one changed a price. Stages 9 and 10 do the untangling, against a tree already shaped to
receive it.

**Prerequisite:** Stage 7 checkpoint passes.

## The target layout

```
api/app/
├── main.py                              # composition root — the ASGI path app.main:app must survive
├── seed.py                              # CLI entrypoint — `python -m app.seed` must survive
├── core/                                # shared by every module; imports no module
│   ├── config.py                        # ← config.py
│   ├── db.py                            # ← db.py
│   ├── errors.py                        # ← errors.py         the one error envelope
│   ├── telemetry.py                     # ← services/telemetry.py
│   ├── ratelimit.py                     # ← services/ratelimit.py
│   └── revalidate.py                    # ← services/revalidate.py
└── modules/
    ├── catalog/
    │   ├── domain/
    │   │   ├── entities/                # ← models/  platform · option_group · option
    │   │   │                            #            option_rule · asset
    │   │   ├── enums.py                 # SelectionMode · DisplayStyle · RuleRelation · AssetKind
    │   │   ├── pricing.py               # ← services/pricing.py   still forbids sqlmodel
    │   │   └── rules.py                 # ← services/rules.py     still forbids sqlmodel
    │   ├── application/                 # Stage 9 puts ports here, Stage 10 use cases
    │   ├── infrastructure/              # Stage 9 puts the repository here
    │   └── presentation/                # ← routers/catalog.py · schemas/catalog.py
    ├── quotes/
    │   ├── domain/
    │   │   ├── entities/                # ← models/quote.py       Quote · QuoteLine
    │   │   ├── enums.py                 # QuoteKind
    │   │   ├── refs.py                  # ← services/refs.py
    │   │   └── spam.py                  # ← services/spam.py
    │   ├── application/
    │   ├── infrastructure/
    │   │   └── mail.py                  # ← services/mailer.py
    │   └── presentation/                # ← routers/quotes.py · schemas/quote.py
    └── admin/
        ├── application/
        └── presentation/                # ← routers/admin.py · schemas/admin.py
```

`app/services/` disappears as a name, and so does the shape that let `mailer.py` import a wire
schema.

**`admin` has no `domain/` and no `infrastructure/`, and that is correct.** It owns no entities and
no tables — it is a guarded read over quotes and platforms. A module carries only the layers it
needs; empty directories holding a lone `__init__.py` are noise that makes the real structure harder
to see.

## One app, many modules

These modules are bounded like services, but **nothing is deployed independently**. One process, one
database, one `SQLModel.metadata`, one Vercel function. The boundary is drawn where a service
boundary would go if it ever needed to — and then not crossed.

Each module owns an `APIRouter` and exports it from its package root. `app/main.py` stays the single
composition root and mounts them:

```python
from app.modules.admin import router as admin_router
from app.modules.catalog import router as catalog_router
from app.modules.quotes import router as quotes_router

app.include_router(catalog_router)
app.include_router(quotes_router)
app.include_router(admin_router)
```

That is the same three lines `main.py` has today. What changes is what sits behind each name: a
module that could be lifted out whole, rather than a router reaching into shared `models/`,
`schemas/`, and `services/` directories that three other routers also reach into.

**The facade rule is what makes that true.** A module may import another module's `application` and
`domain` — its use cases, its ports, its entities. It may **not** import another module's
`presentation` or `infrastructure`. Those are the module's own adapters: its HTTP shapes and its
SQL. The test is simple — *if this module were pulled out and put behind an HTTP call tomorrow,
would this import still make sense?* Calling `catalog`'s `get_platform` use case survives that move.
Reaching into `catalog`'s SQLModel query does not.

What this deliberately does **not** buy, and should not be mistaken for: separate deployables,
per-module schemas or migrations, a network hop between modules, or independent release cadence.
Splitting a monolith is a decision with real costs, and this project — three placeholder platforms
on a free tier — has none of the pressures that justify it. What the layout buys is that the seam
exists and is enforced, so the decision stays available instead of having to be excavated.

## What belongs in `core`

Two tests, and a thing must pass one of them:

- **More than one module uses it.** `revalidate.py` is called by seeding (catalog) and by the admin
  revalidate endpoint. `errors.py` is the single error envelope every router answers with — putting
  it in a module would mean one module owning the others' error shape.
- **It names no module's vocabulary.** `ratelimit.py` counts keys in a window; it knows nothing about
  quotes, even though quotes is its only caller today. `config.py`, `db.py`, and `telemetry.py` are
  the same.

`core` is deliberately **flat, not layered**. Sub-dividing six files into four more directories is
ceremony that would obscure rather than clarify. What `core` does owe is the hard rule below: it may
not import a module, ever.

## The three rules

**The layer rule, inside every module:**

```
presentation : infrastructure  →  application  →  domain
```

`presentation` and `infrastructure` are siblings — both are adapters, neither may import the other.
Both may reach `application`; `application` may reach `domain`; `domain` reaches nothing.

**The module rule, between modules:**

```
admin → quotes → catalog → core
admin ────────────────────↗
```

A DAG, and the arrows only point one way. `quotes` imports `catalog` because pricing a submission
means reading a `Platform` and applying the catalog's own `pricing` and `rules`. `admin` imports
both because it lists leads and revalidates platform slugs. Nothing imports `admin`, and `core`
imports nothing.

**The facade rule, into a module:** another module sees only `application` and `domain`. Stated
above, and checked as its own contract below.

**Cross-module foreign keys stay.** `Quote.platform_id` references `Platform` and
`QuoteLine.option_id` references `Option`, across a module boundary. That is fine: there is one
database and one `SQLModel.metadata`. The module boundary is a boundary in the code, not in the
schema, and pretending otherwise would mean giving up referential integrity to win an argument about
directories.

## Three paths that must not move

| Path | Referenced by |
|---|---|
| `app.main:app` | `pyproject.toml` `[tool.vercel] entrypoint`, `Dockerfile` CMD, `render.yaml` `startCommand` |
| `python -m app.seed` | `.github/workflows/ci.yml` (twice), `README.md`, `docs/setup.md`, `docs/deploy.md` |
| Eager entity imports | `alembic/env.py` — autogenerate only sees tables that have been imported |

`[tool.uv] package = false` with `pythonpath = ["."]` means there is no installed package, so the
restructure needs no packaging change at all.

## Steps

1. **Move, do not edit.** Every file lands in its new module and layer with its body untouched. Use
   `git mv` so the history follows. The only permitted edits are import statements — including the
   two in `alembic/env.py`, where `app.config` becomes `app.core.config` and the single
   `import app.models` becomes one import per module's entities package.
2. **Split `models/enums.py` by module.** `SelectionMode`, `DisplayStyle`, `RuleRelation`, and
   `AssetKind` describe the catalog; `QuoteKind` describes a lead. `admin`'s schemas import
   `QuoteKind` from `quotes`, which is a legal downward dependency, not a leak.
3. **Keep the eager entity imports, one per module.** `models/__init__.py` imports all seven table
   classes so relationship string references resolve regardless of import order and Alembic's
   autogenerate sees every table. That job now belongs to each module's
   `domain/entities/__init__.py`. Trimming either to what looks used produces a migration that
   silently drops tables.
4. **Guard the registry with a test.** Splitting the entity imports across modules introduces a way
   to forget one: a new module whose tables Alembic never sees. Add a test that walks
   `app/modules/*/domain/entities/` and asserts every table class found there is present in
   `SQLModel.metadata.tables`. This is cheap, and it fails at the moment the mistake is made rather
   than in a migration review months later.
5. **Update the tests that import moved paths, in the same commit.** No compatibility shims — a shim
   would let the old path keep working and the move would never finish. Affected:
   `test_quotes_api.py` (`app.db.engine`, `app.routers.quotes.limiter`), `test_admin_api.py` (same
   limiter, plus its walk over `app.routes`), `test_telemetry.py`, `test_mailer.py`,
   `test_pricing.py`, `test_rules.py`, `test_lead_controls.py`. Mirror the module structure in
   `tests/` while you are there, so a test's location says which module it covers.
6. **Add `import-linter`** to the dev dependency group, configured under `[tool.importlinter]` in
   `api/pyproject.toml`. Set `include_external_packages = true`, without which the last two
   contracts cannot name `fastapi`, `httpx` or `sqlmodel` at all. Six contracts — the facade rule
   needs two, one per importable module, because a `forbidden` contract cannot name the same
   package as both source and target and `quotes` is both:
   - **Layers**, applied to all three modules at once with `containers` — one contract, not three,
     so a fourth module is covered the day it is created. `admin` has neither a `domain` nor an
     `infrastructure`, so both are wrapped in parentheses: that is import-linter's syntax for a
     layer that need not exist, and without it the contract errors rather than runs.
   - **Module direction** — `core` is forbidden from importing `app.modules`; `catalog` from
     importing `quotes` or `admin`; `quotes` from importing `admin`.
   - **Module facades** — no module may import another module's `presentation` or `infrastructure`.
     This is the contract that keeps the modules service-shaped; without it the directories are
     decoration and the couplings come back one convenient import at a time.
   - **Domain isolation** — every `domain` is forbidden from importing `fastapi`, `starlette`, and
     `httpx`.
   - **Mirror purity** — `catalog.domain.pricing` and `catalog.domain.rules` are forbidden from
     importing `sqlmodel` and `sqlalchemy`. This is the existing rule from
     [01-backend-catalog.md](01-backend-catalog.md) — until now asserted in a docstring and grepped
     for by hand in the `stage-checkpoint` skill, and from here on checked.

   **Three imports do not survive the move, and are pinned rather than papered over.** This stage
   plan claimed the moved tree would satisfy every contract; it does not, because two of the
   entanglements stages 9 and 10 exist to remove are visible the moment the layout makes them
   visible. Both come down to one fact: `QuoteDetail` is a *wire* schema being used as the quotes
   module's internal currency, and the router calls the mail adapter directly.

   | Import | Rule | Removed by |
   |---|---|---|
   | `quotes.presentation.router → quotes.infrastructure.mail` | layers | Stage 10 — the router calls a use case that owns the mail port |
   | `quotes.infrastructure.mail → quotes.presentation.schemas` | layers | Stage 10 — mail renders a use-case result, not a response schema |
   | `admin.presentation.router → quotes.presentation.schemas` | facade | Stage 10 — admin calls a quotes use case |

   They are listed as named `ignore_imports` entries against the contract each one breaks, with a
   comment naming the stage that deletes it. Fixing them here would mean moving `QuoteDetail` and
   introducing a mail port — code changes, in the commit that is supposed to contain only moves.
   Weakening the contracts instead would hide three couplings behind a rule that no longer says
   anything. An enumerated list of three is neither: it keeps the rule at full strength, and it is
   a countdown that should only ever shrink. `unmatched_ignore_imports_alerting` defaults to
   `error`, so an entry that stops matching fails the build rather than lingering.
7. **Add `uv run lint-imports` to the api job** in `.github/workflows/ci.yml`, after
   `ruff format --check`. A contract nothing runs is a comment.
8. **Set `known-first-party = ["app", "tests"]`** under `[tool.ruff.lint.isort]`. Ruff's `I` rule is
   already enabled; without this it guesses at the new package paths and reshuffles them on the next
   unrelated touch.
9. **Update every path reference this stage invalidates** — `CLAUDE.md`, `docs/architecture.md`
   ("Where things live"), `docs/PLAN.md` (repository layout), and the four skills that name
   `app/models/`, `app/schemas/`, `app/routers/`, or `app/services/`: `catalog-change`,
   `pricing-mirror`, `alembic-migration`, `stage-checkpoint`. `catalog-change` changes most: its
   seven-files-in-four-directories chain becomes a walk down one module.

## Checkpoint

Capture the wire output **before** touching anything:

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
curl -s localhost:8000/v1/catalog | jq -S . > /tmp/catalog.before.json
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . > /tmp/platform.before.json
```

Then, after the move:

```bash
cd api
uv sync
uv run ruff check . && uv run ruff format --check .
uv run lint-imports
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

# No pending migration: the move must not have changed the schema.
uv run alembic check

curl -s localhost:8000/v1/catalog | jq -S . | diff /tmp/catalog.before.json -
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . | diff /tmp/platform.before.json -

# The stage records under docs/stages/ are excluded on purpose: 01 and this file describe the
# layout as it was and the move itself, which is history rather than a live path reference.
grep -rn "app/models\|app/schemas\|app/routers\|app/services" \
  ../CLAUDE.md ../docs ../.claude/skills ../README.md ../web/src | grep -v "docs/stages/0[18]"
# no hits
```

## Done when

Both golden diffs are empty, `alembic check` reports no pending changes, `uv run lint-imports` is
green in CI with all six contracts, and no document, skill or source comment in the repository names
a directory that no longer exists.
