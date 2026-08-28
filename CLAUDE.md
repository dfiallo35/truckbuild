# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TruckBuild — a marketing site plus per-platform build configurator for a truck upfitting company. A visitor
picks a platform, configures option groups, watches the price update live, and submits the build as a lead.

Two services, no monorepo tooling tying them together — each is installed and run from its own directory:

- `web/` — Next.js 16 (App Router), TypeScript, Tailwind 4, pnpm
- `api/` — FastAPI, SQLModel, Alembic, Postgres, uv

## Commands

Backend (`cd api`):

```bash
uv sync                        # install
uv run uvicorn app.main:app --reload
uv run pytest                  # all tests
uv run pytest tests/test_health.py::test_healthz_reports_ok   # one test
uv run ruff check .            # lint
uv run ruff format .           # format (CI runs `ruff format --check .`)
uv run lint-imports            # module, layer and facade contracts (pyproject.toml)
```

Frontend (`cd web`):

```bash
pnpm install                   # add --fetch-timeout 600000 on slow connections
pnpm dev                       # :3000
pnpm build
pnpm lint                      # eslint
pnpm test                      # vitest run — the TS half of the pricing mirror
pnpm e2e                       # playwright — configurator, a11y (axe), responsive
pnpm bundle:check              # per-route client JS budgets (run after `pnpm build`)
pnpm format                    # prettier --write .  (CI runs `prettier --check .`)
```

`pnpm e2e` starts its own production server. Point it at a deployment with
`E2E_BASE_URL=https://… pnpm e2e` — that is how the production smoke test is run. Specs live in
`web/e2e/` (Playwright), not `web/tests/` (Vitest); the two runners must not share a directory.

Stack:

```bash
docker compose up -d           # Postgres + API with hot reload on :8000
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
```

Postgres is published on host port **5433**, not 5432, to avoid colliding with a host Postgres. Inside the
Compose network the API still reaches it at `db:5432`.

## Architecture

### The central tension

FastAPI owns the catalog, but a marketing site needs fast, prerendered, SEO-indexable pages. The resolution
drives most structural decisions and is documented in `docs/decisions.md`:

- `cacheComponents: true` in `web/next.config.ts` (Next.js 16 Cache Components / PPR). Catalog reads live
  inside `'use cache'` functions tagged `cacheTag('catalog')` and `cacheTag('platform-<slug>')`. Pages render
  from cache, so a slow or down API does not take the marketing site with it. **If `pnpm build` output stops
  showing `- Cache Components enabled`, every caching assumption in the design is void.**
- When catalog rows change, FastAPI POSTs to the web app's `/api/revalidate` with `REVALIDATE_SECRET`; that
  route calls `revalidateTag`.
- `api/seed/catalog.yaml` is the versioned source content, loaded idempotently (upsert by slug) by
  `app/seed.py`. Postgres remains the runtime source of truth.

### Boundaries that must hold

- **`app/modules/catalog/domain/pricing.py` and `.../domain/rules.py` are pure** — no `fastapi`, no
  `sqlmodel` imports. That is what makes them cheap to test and safe to mirror on the client. Write them
  test-first. Enforced by the `Pricing mirror purity` import contract.
- **The pricing mirror is deliberate duplication.** `price_build` exists in Python (authoritative) and in
  `web/src/lib/pricing.ts` (instant UI feedback). Both sides must be tested against a **single shared JSON
  fixture file** consumed by pytest and Vitest — that is the only thing keeping them from drifting. Same for
  `validate_selection`.
- **The server price is authoritative.** `POST /v1/quotes` re-validates the selection and recomputes the
  total, ignoring any client-supplied price.
- **The browser never sees the API origin.** `API_BASE_URL` is server-side only and must never be prefixed
  `NEXT_PUBLIC_`; the browser reaches FastAPI only through Server Actions and route handlers.
- **`web/src/lib/api.ts` parses every backend response with Zod** rather than casting, so a backend shape
  change surfaces as a named field error instead of a runtime `undefined` inside a component.
- **Every env var is declared in `app/core/config.py`** (pydantic-settings) so a missing value fails at startup.
- **Slugs are the public identifiers** — they appear in URLs and shared builds. Renaming one is a breaking
  change.

### The API is a modular monolith

`api/app/` is one FastAPI app assembled at one composition root (`main.py`) out of feature modules under
`app/modules/`, each carrying its own layers over a shared `app/core/`. One process, one database, one
`SQLModel.metadata` — nothing is deployed independently. Seven rules, all checked by
`uv run lint-imports` (contracts in `api/pyproject.toml`, rationale in
`docs/stages/08-modules-and-layers.md`, `docs/stages/09-core-kernel.md` and
`docs/stages/10-catalog-slice.md`):

- **Layers, inside every module:** `presentation : infrastructure → application → domain`. The two
  adapters are siblings and neither may import the other; `domain` imports nothing.
- **The same layers inside `core`.** The kernel is a module in every respect except that everything
  may import it. `config.py` sits outside the layers on purpose: every layer reads it and it belongs
  to none.
- **Kernel purity:** `app/core/domain/` and `app/core/application/` name no ORM and no web framework.
  `BaseEntity` is what every module's entities move onto in stages 10–12, so an impure base class
  would make each of them impure by inheritance.
- **Module direction:** `admin → quotes → catalog → core`, a DAG, arrows one way only. `core` imports no
  module, ever, and a thing belongs in `core` only if more than one module uses it *or* it names no
  module's vocabulary.
- **Facades:** another module sees only your `application` and `domain` — never your `presentation` or
  `infrastructure`. The test is *if this module went behind an HTTP call tomorrow, would this import
  still make sense?*
- **`domain` names no ORM** (`Domain forbids persistence`). True of `core` and of `catalog`; widened to
  `quotes` in stage 11. This is the line that measures whether the migration worked.
- **`presentation` names no ORM** (`Presentation forbids persistence`). Direct imports only — indirectly
  every router reaches Postgres, which is what an endpoint is for. `catalog` today, the rest by stage 12.

A module carries only the layers it needs (`admin` owns no tables, so it has no `domain` and no
`infrastructure`). Cross-module foreign keys are fine — the boundary is in the code, not the schema.
Three imports are pinned as named `ignore_imports` exceptions with the stage that removes each;
that list should only ever shrink.

**Nothing may import an adapter, so `main.py` binds every port.** Between the sibling-adapter rule,
the facade rule, and import-linter following whole chains rather than direct imports, there is no
legal path from a router to a repository. So each `presentation` declares what it needs as a
dependency that raises `NotImplementedError`, each module's `dependencies.py` builds the concrete
thing, and `PORT_BINDINGS` in `app/main.py` joins them through `app.dependency_overrides` — the
application's entire cross-layer and cross-module wiring, in one screen.
`tests/test_composition_root.py` discovers the declared ports from the source and fails if one is
left unbound. A module's **`dependencies.py` sits beside its four layers, not inside one**, for the
same reason `core/config.py` sits beside the kernel's: it is the one file that has to see an
adapter and an inner layer at once.

**The kernel a module is built out of** lives in `app/core/`, laid out in the same four layers and
adapted from [`dfiallo35/property-management`](https://github.com/dfiallo35/property-management):

- `core/domain/` — `BaseEntity` (pure pydantic, integer key), `IBaseRepository`, `IRateLimiter`,
  `BaseFilter`, `BaseError`, `UseCaseEnum`.
- `core/application/` — `BaseUseCase`, a template method driving `pre_run → validate → run →
  post_run`, plus its CRUD subclasses; `BaseService`, which wires a mapper, a filter class and a
  repository into them; `BaseMapper` (domain ↔ DTO); the DTOs, including the one error body.
- `core/infrastructure/postgres/` — `BaseTable` (`id`, `created_at`, `updated_at`), `UTCDateTime`,
  `BaseMapper` (table ↔ domain), `BaseRepositoryPostgres`, the engine and session.
- `core/presentation/` — `create_app`, the exception handlers, telemetry, query-parameter filters.

**Write a use case by overriding a hook, never `exec`.** `BaseFilter`'s `_eq` / `_in` / `_ilike` /
`_gte` / `_lte` suffixes are load-bearing: `BaseRepositoryPostgres.filter` keys off exactly those
names, so a field called `created_after` is silently ignored. The named deviations from the
reference repo — FastAPI `Depends` rather than `dependency_injector`, sync rather than async,
`limit`/`offset` rather than `page`/`size`, SQLModel tables, no i18n — are in
`docs/stages/09-core-kernel.md`.

**`catalog` is the finished shape; `quotes` and `admin` are not there yet:**

- `catalog/domain/` is pure pydantic — `Platform`, `OptionGroup`, `Option`, `OptionRule` and `Asset`
  in `models.py`, with the SQLModel tables and the mapper between them in
  `infrastructure/postgres/`. `quotes`' entities still *are* SQLModel tables until stage 11.
- `PlatformRepositoryPostgres.list` reads the whole catalog in a **fixed five statements** whatever
  it is asked for; a domain `Platform` carries its groups, options, assets and rules as loaded
  values, so no layer above the repository can trigger a query by reading an attribute.
  `tests/modules/catalog/test_catalog_queries.py` seeds a fourth platform and asserts the count
  does not move.
- `catalog`'s router writes no query. `quotes`' and `admin`'s still do, until stages 11 and 12.

### Build state

Configurator selection is encoded in the URL query string (`?o=slug-a,slug-b`), which gives shareable,
refresh-safe, back-button-correct builds with no database round trip. `web/src/lib/build.ts` owns the
encoding; it repairs a URL rather than trusting it (unknown slugs dropped, single-select groups
de-duplicated, required groups defaulted) because a shared build URL outlives the catalog it was
built from. The URL is written with `history.replaceState`, not a router navigation.

### Route groups

Marketing pages live under `web/src/app/(site)/`, whose layout carries `Header` and `Footer`. The root
layout holds only the document shell. `/configurator/[slug]` sits outside that group so it can be
full-bleed with its own minimal bar — a nested layout cannot remove a parent's chrome. Route groups add
no URL segment, so paths are unaffected.

## Working in this repo

**The repo is indexed by CodeGraph.** `codegraph explore "<symbol or question>"` (or the
`codegraph_explore` MCP tool) returns the verbatim source of the relevant symbols plus the call paths
and blast radius between them, across `api/` and `web/` in one query — reach for it before grep when
locating or understanding code. Most work here crosses the two services, which is exactly where a
grep-per-directory loop leaves a link out. The index at `.codegraph/` is local machine state, rebuilt
from source and gitignored; it can go stale after large refactors, so treat a symbol it names as a
claim to verify, not a fact. Skip it for non-symbol text — a YAML key, a slug string, a hex color.

**`gh` is not installed on this machine.** GitHub operations — PRs, issues, checks, reviews — go
through the GitHub MCP tools (`mcp__github__*`), which are deferred and must be loaded with
`ToolSearch("select:...")` before they can be called. Repo coordinates are `dfiallo35/truckbuild`,
base `main`. Ordinary git (branch, commit, push) still works through Bash.

**A task is finished when its work is in a pull request**, not when it is committed locally. Run the
CI-equivalent sweep, then open the PR with the `open-pr` skill. Branch off a freshly fetched
`origin/main` — local `main` goes stale as soon as a PR is merged through the web UI — and never
commit to `main` directly. If an open PR already covers the same concern, add a commit to it instead
of opening a second one that will conflict.

The build is split into staged, independently reviewable steps in `docs/PLAN.md`, each with its own
file under `docs/stages/` containing steps, a runnable checkpoint, and done-when criteria. **Read the current
stage's file before starting work on it**, and don't start a stage until the previous checkpoint passes.
Stages 0–10 are complete. Stage 8 moved `api/` into the modular-monolith layout described above,
stage 9 built the `core` kernel every module extends, and stage 10 moved `catalog` onto it; stages
11–12 do the same for `quotes` and `admin`, then seeding, web and docs (13). Every one of
those stages keeps the wire contract byte-identical and diffs against the golden capture in
`api/tests/golden/` to prove it. The site is deployed at <https://truckbuild.vercel.app>
with the API at <https://truckbuild-api.vercel.app>; see `docs/deploy.md`, which is the runbook
and also records why the API runs as a Vercel Python function rather than the container
`api/render.yaml` still describes.

Supporting docs: `docs/domain-model.md` (entities, vocabulary, the placeholder catalog and its compatibility
rules), `docs/testing.md` (what each layer tests and with which tool), `docs/decisions.md` (locked-in choices,
accepted risks, explicitly deferred scope).

Stage 2 asks for the `frontend-design` skill to be loaded before any visual work — the dark, cinematic
direction is the product there, and framework defaults will read as templated. Design tokens go in
`globals.css` and map into the Tailwind theme; no component hardcodes a color.

Catalog names, prices, and specs (Bristlecone / Ironwood / Sentinel) are demo placeholders to be replaced
with the real company's data.

## Project skills

`.claude/skills/` holds skills for the tasks in this repo that cross service boundaries and are easy to
leave half-finished. Claude invokes them automatically when relevant; you can also call one by name.

| Skill | Use when |
|---|---|
| `pricing-mirror` | Touching pricing arithmetic or compatibility rules on either side of the Python/TypeScript mirror |
| `catalog-change` | Adding or editing a platform, option, price, or rule — the chain from `catalog.yaml` to a rendered page |
| `cache-and-revalidation` | Adding a catalog read, changing cache tags, or a catalog edit not reaching the site |
| `alembic-migration` | Any change to a module's tables — `catalog/infrastructure/postgres/tables.py`, `quotes/domain/entities/` |
| `stage-checkpoint` | Verifying or closing out a stage, or running the CI-equivalent sweep |
| `open-pr` | Opening or inspecting a PR — the last step of any task that produces committed work |

## Gotchas recorded from the build

- `RUN --mount=type=cache` requires BuildKit, which is not enabled on every daemon. `api/Dockerfile`
  deliberately avoids cache mounts.
- **Adding a Python dependency needs `docker compose up -d --build --renew-anon-volumes api`.** The
  Compose file keeps an anonymous volume on `/srv/.venv` so the bind-mounted host source does not
  shadow the image's virtualenv — and Docker reuses that volume across rebuilds, so `--build` alone
  leaves the container running the old venv. It fails as `ModuleNotFoundError` for a package that is
  plainly installed, and the API then hangs rather than erroring, which reads like a database problem.
- Never pipe a command whose exit status matters (e.g. `pnpm install`) through `tail` — it masks the
  exit code.
