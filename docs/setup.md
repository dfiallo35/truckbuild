# Setup

Getting TruckBuild running locally, and the commands you will use afterwards. For deploying it, see
[deploy.md](deploy.md); for how it fits together, [architecture.md](architecture.md).

## Prerequisites

| Tool | Used for | Notes |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) + Compose | Postgres and the API | The fastest path; skip it only if you want to run Python natively |
| [uv](https://docs.astral.sh/uv/) | The Python service | Only needed for the native path, or to run `pytest`/`ruff` outside the container |
| [Node 20+](https://nodejs.org) and [pnpm](https://pnpm.io) | The web app | pnpm, not npm — the lockfile is pnpm's |

Nothing here needs a global Python or a virtualenv you manage yourself; `uv` handles both.

## First run

```bash
cp .env.example .env      # then edit as needed; the defaults work as-is for local
```

### 1. Backend

```bash
docker compose up -d                                  # Postgres + API, hot reload, :8000
docker compose exec api alembic upgrade head          # create the tables
docker compose exec api python -m app.seed            # load seed/catalog.yaml
curl localhost:8000/healthz
```

You should get `{"status":"ok","environment":"development"}`.

> **Postgres is published on host port 5433, not 5432**, so it does not collide with a Postgres
> already running on your machine. Inside the Compose network the API still reaches it at `db:5432`.

```bash
psql postgresql://truckbuild:truckbuild@localhost:5433/truckbuild
```

The seed is idempotent — it upserts by slug — so re-running it is always safe, and re-running it is
how you load a catalog edit.

### 2. Frontend

```bash
cd web
pnpm install              # add --fetch-timeout 600000 on a slow connection
pnpm dev                  # :3000
```

Open <http://localhost:3000>. If the platform cards show no prices, the API is not up or
`API_BASE_URL` is wrong.

### Running the API natively instead

Useful when you are iterating on Python and want a debugger attached:

```bash
docker compose up -d db   # keep Postgres in Compose
cd api
uv sync
uv run uvicorn app.main:app --reload
```

`app/config.py` defaults `DATABASE_URL` to `localhost:5433`, so this works with no extra
configuration.

## Environment variables

Every one is documented in [`.env.example`](../.env.example), and every one the API reads is declared
in `api/app/core/config.py` — a missing or malformed value fails at startup rather than surfacing as a
confusing `None` inside a request.

Four are worth calling out:

| Variable | Why it matters |
|---|---|
| `API_BASE_URL` | **Server-side only.** Never prefix it `NEXT_PUBLIC_` — the browser must not learn the API origin |
| `REVALIDATE_SECRET` | Must be **byte-identical** on both services. When it drifts nothing fails loudly; catalog edits simply stop reaching the site |
| `CORS_ORIGINS` | JSON array, not a bare string. It is typed `list[str]`, so `CORS_ORIGINS=https://x` fails at startup and `["https://x"]` is correct |
| `DATABASE_URL` | Needs the `+psycopg` driver prefix. Plain `postgresql://` fails with a driver error |

`web/.env.local` holds the web app's local values. Note that `vercel link` **overwrites** that file,
so if you run it, put `API_BASE_URL` and `REVALIDATE_SECRET` back.

## Commands

### Backend — from `api/`

| Command | What it does |
|---|---|
| `uv sync` | Install dependencies |
| `uv run uvicorn app.main:app --reload` | Run the API |
| `uv run pytest` | All tests |
| `uv run pytest tests/test_health.py::test_healthz_reports_ok` | One test |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format — **CI runs `ruff format --check .`** |
| `uv run alembic upgrade head` | Apply migrations |
| `uv run python -m app.seed` | Load the catalog and revalidate the site's cache |
| `uv run python -m app.seed --no-revalidate` | Load it without telling the web app |

### Frontend — from `web/`

| Command | What it does |
|---|---|
| `pnpm install` | Install dependencies |
| `pnpm dev` | Dev server on :3000 |
| `pnpm build` | Production build |
| `pnpm start` | Serve the production build |
| `pnpm test` | Vitest — the TypeScript half of the pricing mirror |
| `pnpm e2e` | Playwright — configurator, accessibility (axe), responsive |
| `pnpm bundle:check` | Per-route client JS budgets — **run after `pnpm build`** |
| `pnpm lint` | ESLint |
| `pnpm format` | Prettier — **CI runs `prettier --check .`** |

### The CI-equivalent sweep

What GitHub Actions runs. A change is not finished while this would be red:

```bash
cd api
uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

cd ../web
pnpm install --frozen-lockfile && pnpm lint && pnpm exec prettier --check . && pnpm test && pnpm build
```

> **Never pipe any of these through `tail` or `head`.** The pipe replaces the command's exit status
> with the pager's, so a failing suite reports success. This repo has been bitten by it. Redirect to
> a file instead and read that; the exit code stays intact.

### End-to-end specs

`pnpm e2e` starts its own **production** server on port 3100 — not `next dev`, because prerendering
and Cache Components behave differently in development and those are exactly what the specs check.

```bash
cd web
pnpm e2e                                                # local production build
E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e     # the deployed site
```

`configurator.spec.ts` and `a11y.spec.ts` are read-only and safe to point anywhere. `quote.spec.ts`
stores a real lead and emails sales, so it skips itself against a non-local target unless
`E2E_ALLOW_WRITES=1` says otherwise.

## Making changes

Some changes cross both services, and the repo has skills that walk the whole chain so nothing is
left half-wired. Claude invokes them automatically; you can also call one by name.

| Skill | Use when |
|---|---|
| `pricing-mirror` | Touching pricing arithmetic or compatibility rules on either side of the Python/TypeScript mirror |
| `catalog-change` | Adding or editing a platform, option, price, or rule — the chain from `catalog.yaml` to a rendered page |
| `cache-and-revalidation` | Adding a catalog read, changing cache tags, or a catalog edit not reaching the site |
| `alembic-migration` | Any change to a module's tables — `catalog/` or `quotes/infrastructure/postgres/tables.py` |
| `stage-checkpoint` | Verifying a stage, or running the CI-equivalent sweep |
| `open-pr` | Opening or inspecting a PR |

The repo is also indexed by **CodeGraph** (a `.codegraph/` directory at the root, gitignored local
state). `codegraph explore "<symbol or question>"` returns the relevant source plus call paths across
both services in one query — reach for it before grep when locating code, since most work here
crosses the service boundary and a grep-per-directory loop leaves the link out.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `ModuleNotFoundError` for a package that is plainly installed, and the API hangs rather than erroring | You added a Python dependency. Compose keeps an anonymous volume on `/srv/.venv` and Docker **reuses it across rebuilds**, so `--build` alone leaves the old virtualenv. Run `docker compose up -d --build --renew-anon-volumes api`. It reads like a database problem and is not |
| Configurator stuck on "Loading build" forever; every `/_next/static/chunks/*.js` 404s | A `next dev` server is rewriting `.next` underneath your production build, so the served HTML references chunk hashes from a different build. **Stop the dev server**, `rm -rf .next`, rebuild |
| Playwright passes or fails for no apparent reason | Something is serving port 3000 that is not what you built. The suite deliberately uses 3100 and never reuses an existing server |
| `pnpm build` no longer prints `- Cache Components enabled` | `next.config.ts` is not being picked up, and every caching assumption in the design is void. Fix this before anything else |
| Catalog edit is correct in Postgres but stale on the site | `REVALIDATE_SECRET` differs between the services, or the seed ran with `--no-revalidate` |
| Revalidation from the API silently does nothing | Inside Compose, `localhost:3000` is the *container*. `WEB_BASE_URL` must be `http://host.docker.internal:3000`, which the Compose file already sets |
| API will not start, driver error | `DATABASE_URL` is missing the `+psycopg` prefix |
| API will not start, settings error | `CORS_ORIGINS` is a bare string instead of a JSON array |
| `pnpm install` times out mid-fetch | Slow connection — `pnpm install --fetch-timeout 600000` |
| A build URL 404s | A platform slug was renamed. Slugs are public identifiers; renaming one is a breaking change |
