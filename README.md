# TruckBuild

Marketing site and build configurator for a company that upfits trucks for different purposes.

A visitor picks a build platform, configures it through option groups, watches the price update live,
and submits the finished build as a qualified lead.

**Live:** [truckbuild.vercel.app](https://truckbuild.vercel.app) · API at
[truckbuild-api.vercel.app](https://truckbuild-api.vercel.app)

> Catalog names, prices, specs, and photography are demo placeholders standing in for the real
> company's data.

---

## Documentation

| Document | What it covers |
|---|---|
| **[Setup](docs/setup.md)** | Prerequisites, first run, every command, and troubleshooting |
| **[Architecture](docs/architecture.md)** | How the two services fit together, the boundaries that must hold, and why |
| **[Features](docs/features.md)** | What the site does, page by page, and the mechanics behind the configurator |
| **[Deploying](docs/deploy.md)** | The runbook — Neon, both Vercel projects, secrets, and failure modes |
| **[Decisions](docs/decisions.md)** | Locked-in choices, accepted risks, and what was deliberately deferred |
| **[Domain model](docs/domain-model.md)** | Entities, vocabulary, and the placeholder catalog |
| **[Testing](docs/testing.md)** | What each layer tests, with which tool, and why the split is load-bearing |
| **[Plan (archived)](https://app.notion.com/p/3ce774db73568150bcd2cb9e6b099239)** | The 18 build stages that shipped this app, each with its own checkpoint — moved to Notion once the staged build finished |

New to the project? [Setup](docs/setup.md) to get it running, then
[Architecture](docs/architecture.md) to understand the shape of it.

---

## Quick start

```bash
cp .env.example .env

docker compose up -d                             # Postgres + API on :8000
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed

cd web && pnpm install && pnpm dev                # :3000
```

Postgres is published on host port **5433**, not 5432, so it does not collide with a Postgres already
on your machine. Full instructions, the native-Python path, and troubleshooting are in
[docs/setup.md](docs/setup.md).

## The two services

No monorepo tooling ties them together — each is installed and run from its own directory.

| Service | Stack | Responsibility |
|---|---|---|
| `web/` | Next.js 16, TypeScript, Tailwind 4, pnpm | Marketing pages and the configurator UI |
| `api/` | FastAPI, SQLModel, Alembic, Postgres, uv | Catalog, authoritative pricing, quote submission, admin |

The API owns the catalog. The web app reads it through Next.js **Cache Components**, so marketing
pages prerender and stay up even when the API is slow, and FastAPI pushes a cache invalidation when
catalog rows change. That tension and its resolution is the most important thing about this codebase
— see [Architecture](docs/architecture.md#the-central-tension-and-how-it-is-resolved).

## Commands

| Command | What it does |
|---|---|
| `cd api && uv run pytest` | Backend tests |
| `cd api && uv run ruff check .` | Backend lint |
| `cd api && uv run ruff format .` | Backend format |
| `cd web && pnpm dev` | Dev server on :3000 |
| `cd web && pnpm build` | Production build |
| `cd web && pnpm test` | Frontend unit tests (Vitest) |
| `cd web && pnpm e2e` | End-to-end and accessibility specs (Playwright + axe) |
| `cd web && pnpm bundle:check` | Per-route client JS budgets, after a build |
| `cd web && pnpm lint` | Frontend lint |
| `cd web && pnpm format` | Frontend format |

`pnpm e2e` starts its own production server. Point it at a deployment with
`E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e`. The full list, including the CI-equivalent
sweep, is in [docs/setup.md](docs/setup.md#commands).

## Deploying

Neon, then the API, then the web app — in that order, because each needs the one before it. Both
services are Vercel projects, distinguished by their Root Directory (`api` and `web`); Postgres is
Neon. The whole stack is on free tiers.

The runbook, the secrets, what the free tiers cost you in exchange, and why the API is *not* on
Render are in [docs/deploy.md](docs/deploy.md).

## Environment variables

All are documented in [`.env.example`](.env.example), and every one the API reads is declared in
`api/app/config.py` so a missing value fails at startup. Two are worth calling out here:

- **`API_BASE_URL`** is server-side only. It must never be prefixed `NEXT_PUBLIC_`; the browser talks
  to the API only through Next.js Server Actions and route handlers.
- **`REVALIDATE_SECRET`** must match between the two services, or catalog edits will not reach the
  site — silently.
