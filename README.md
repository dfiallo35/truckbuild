# TruckBuild

Marketing site and build configurator for a company that upfits trucks for different purposes.

A visitor picks a build platform, configures it through option groups, watches the price update live, and
submits the finished build as a qualified lead.

## Architecture

Two services:

| Service | Stack | Responsibility |
|---|---|---|
| `web/` | Next.js 16, TypeScript, Tailwind 4 | Marketing pages and the configurator UI |
| `api/` | FastAPI, SQLModel, Postgres | Catalog, authoritative pricing, quote submission, admin |

The API owns the catalog. The web app reads it through Next.js **Cache Components**, so marketing pages
prerender and stay up even when the API is slow — see [docs/decisions.md](docs/decisions.md).

## Plan

The build is split into eight reviewable stages: [docs/PLAN.md](docs/PLAN.md).

## Setup

```bash
cp .env.example .env      # then edit as needed
```

### Backend

```bash
docker compose up -d      # Postgres + API with hot reload on :8000
curl localhost:8000/healthz
```

Postgres is published on host port **5433**, not 5432, so it does not collide with a Postgres already
running on the host. Inside the Compose network the API still reaches it at `db:5432`.

```bash
psql postgresql://truckbuild:truckbuild@localhost:5433/truckbuild
```

Or run it directly against a local Postgres:

```bash
cd api
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd web
pnpm install
pnpm dev                  # :3000
```

## Commands

| Command | What it does |
|---|---|
| `cd api && uv run pytest` | Backend tests |
| `cd api && uv run ruff check .` | Backend lint |
| `cd api && uv run ruff format .` | Backend format |
| `cd web && pnpm build` | Production build |
| `cd web && pnpm test` | Frontend unit tests (Vitest) |
| `cd web && pnpm e2e` | End-to-end and accessibility specs (Playwright + axe) |
| `cd web && pnpm bundle:check` | Per-route client JS budgets, after a build |
| `cd web && pnpm lint` | Frontend lint |
| `cd web && pnpm format` | Frontend format |

`pnpm e2e` starts its own production server. Point it at a deployment with
`E2E_BASE_URL=https://… pnpm e2e`.

## Deploying

Live: **<https://truckbuild.vercel.app>** (site) and **<https://truckbuild-api.vercel.app>** (API).

Neon, then the API, then the web app — in that order, because each needs the one before it. Both
services are Vercel projects, distinguished by their Root Directory (`api` and `web`); Postgres is
Neon. The whole stack is on free tiers. The runbook, the secrets, the failure modes, and what the
free tiers cost you in exchange are in [docs/deploy.md](docs/deploy.md).

## Environment variables

All are documented in [`.env.example`](.env.example). Two are worth calling out:

- **`API_BASE_URL`** is server-side only. It must never be prefixed `NEXT_PUBLIC_`; the browser talks to the
  API only through Next.js Server Actions and route handlers.
- **`REVALIDATE_SECRET`** must match between the two services, or catalog edits will not reach the site.
