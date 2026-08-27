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

- **`app/services/pricing.py` and `app/services/rules.py` are pure** — no `fastapi`, no `sqlmodel` imports.
  That is what makes them cheap to test and safe to mirror on the client. Write them test-first.
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
- **Every env var is declared in `app/config.py`** (pydantic-settings) so a missing value fails at startup.
- **Slugs are the public identifiers** — they appear in URLs and shared builds. Renaming one is a breaking
  change.

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

### Deployment

Live at <https://truckbuild.vercel.app>, API at <https://truckbuild-api.vercel.app>, Postgres on Neon.
**Two Vercel projects from this one repo**, distinguished by Root Directory: `truckbuild` (`web`) and
`truckbuild-api` (`api`, running FastAPI as a Python function). Both deploy on push to `main`.

Three things about it that are not guessable and that fail silently:

- **A deploy does not run migrations.** There is no start hook on a Python function. A
  migration-dependent change deploys *successfully* and then fails its queries. Migrate by hand
  against Neon's **direct** URL before merging — see the `alembic-migration` skill.
- **`api/vercel.json` must declare `{"framework": "fastapi"}`.** Without it Vercel builds the project
  as Node, finishes in ~50ms having built no function, reports success, and every route 404s.
- **The deployed API uses Neon's pooled endpoint**; Alembic and the seed use the direct one. Frozen
  function instances hold their connections.

`api/render.yaml` and `api/Dockerfile` are **dead config** — a complete description of the container
deployment, kept as the thing to return to on a paid plan. Nothing reads them. Don't treat them as
what production does.

Vercel and Neon are both reachable over MCP (deferred — load with `ToolSearch`), and the `vercel` CLI
is installed and authenticated. Environment variables go through the CLI; there is no MCP tool for
them, and changing one does not redeploy.

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

**All eight stages (0–7) are complete and the site is live**, so ordinary feature work is the mode now
— there is no "next stage" to pick up. The staged build is recorded in `docs/PLAN.md` and
`docs/stages/`; those files are a **historical record of how the build went**, not a description of the
present, and rewriting them to match today would destroy the thing that makes them useful.

Documentation, all indexed from `README.md`:

| Doc | For |
|---|---|
| `docs/architecture.md` | How the two services fit together and the boundaries that must hold |
| `docs/setup.md` | Running it locally, every command, the CI sweep, troubleshooting |
| `docs/features.md` | What the site does, page by page, and the configurator mechanics |
| `docs/deploy.md` | The deployment runbook and its failure modes |
| `docs/decisions.md` | Locked-in choices, accepted risks, deferred scope |
| `docs/domain-model.md` | Entities, vocabulary, the placeholder catalog and its rules |
| `docs/testing.md` | What each layer tests, with which tool |

When you change how the system works, the doc that describes it is part of the change. Two documents
went stale for exactly one session after the API moved hosts, and both stated the old arrangement
confidently — which is worse than saying nothing.

**Load the `frontend-design` skill before any visual work.** The dark, cinematic direction *is* the
product on this site, and framework defaults will read as templated against it — this was Stage 2's
instruction and it still stands for every change to the UI. Design tokens live in `globals.css` and map
into the Tailwind theme; no component hardcodes a color.

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
| `alembic-migration` | Any change under `api/app/models/` |
| `deploy` | Deploying, changing an env var on either service, or diagnosing the live site |
| `stage-checkpoint` | Running the CI-equivalent sweep, or verifying against the deployment |
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
  exit code. Redirect to a file and capture `$?` instead.
- **`next dev` and `next build` cannot share a directory.** A dev server left running rewrites `.next`
  underneath a production build, leaving prerendered HTML that references chunk hashes from a
  different build. Every static asset then 404s, `nosniff` refuses the 404 body, and the configurator
  sits on its Suspense fallback forever — a failure that looks exactly like a hydration bug and is
  not. Stop the dev server, `rm -rf .next`, rebuild.
- **Playwright runs on port 3100 and never reuses a server.** `reuseExistingServer` on 3000 silently
  attaches to whatever `next dev` is serving, so the suite passes or fails for reasons unrelated to
  the build under test. The config also sets `channel: "chromium"`: `playwright install --no-shell`
  skips `chrome-headless-shell`, which is exactly what default headless mode launches, so every spec
  fails with "Executable doesn't exist".
- **The first request to the deployment pays a cold start.** One spec timing out on `page.goto` while
  the rest pass is a boot, not a regression. `playwright.config.ts` raises the timeout only when
  `E2E_BASE_URL` is remote.
- **`vercel link` overwrites `.env.local`** in the directory it runs in, silently dropping local dev
  values. Put `API_BASE_URL` and `REVALIDATE_SECRET` back afterwards.
- **Prettier's scope is `web/` only.** Markdown at the repo root and in `docs/` is not format-checked
  by CI, so don't expect `prettier --check` to catch anything there.
