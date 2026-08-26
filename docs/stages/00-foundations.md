# Stage 0 — Foundations

> **Status: complete.** Checkpoint verified 2026-08-26.

**Goal:** both services scaffolded, running locally under Docker Compose, with linting and CI green.
Nothing product-specific yet — this stage only has to prove the machine turns over.

## Steps

1. **Scaffold `web/`** — `pnpm create next-app` (TypeScript, Tailwind, App Router, `src/`, ESLint,
   `@/*` alias). Set `cacheComponents: true` in `next.config.ts`. Initialize shadcn/ui.
2. **Scaffold `api/`** — `uv init`; add `fastapi`, `uvicorn[standard]`, `sqlmodel`, `alembic`,
   `psycopg[binary]`, `pydantic-settings`, `httpx`; dev deps `pytest`, `pytest-asyncio`, `ruff`.
3. **`app/config.py`** — `pydantic-settings` reading every env var, so a missing variable fails loudly at
   startup rather than as a confusing `None` later.
4. **`app/main.py`** — FastAPI app with a `/healthz` endpoint and CORS configured from settings.
5. **`docker-compose.yml`** — Postgres 17 with a named volume, plus the api service with hot reload and a
   healthcheck-gated `depends_on`.
6. **`.env.example`** — `DATABASE_URL`, `API_BASE_URL`, `ADMIN_TOKEN`, `REVALIDATE_SECRET`,
   `RESEND_API_KEY`, `SALES_INBOX`. Commit the example; never the real `.env`.
7. **`.gitignore`** — cover `.env`, `node_modules/`, `.next/`, `__pycache__/`, `.venv/`.
8. **`README.md`** — setup and run commands someone can follow without asking questions.
9. **Lint config** — Ruff for Python, ESLint + Prettier for TypeScript.
10. **CI** — a GitHub Actions workflow running Ruff, `pytest`, and `pnpm build`.

## Checkpoint

```bash
docker compose up -d
curl -s localhost:8000/healthz     # {"status":"ok","environment":"development"}
cd api && uv run ruff check . && uv run pytest -q
cd web && pnpm lint && pnpm exec prettier --check . && pnpm build
```

The build output must include `- Cache Components enabled`; if it does not, `next.config.ts` is not
being picked up and every later caching assumption is void.

## Notes from the build

Three things bit during this stage and are worth remembering:

- **`RUN --mount=type=cache` requires BuildKit**, which is not enabled on every daemon. The Dockerfile
  avoids cache mounts so it builds under the classic builder too.
- **Postgres is published on host port 5433**, not 5432, because a natively-installed Postgres commonly
  already holds 5432. Inside the Compose network the API still uses `db:5432`.
- **`pnpm install` times out on slow connections** and, when piped to `tail`, reports a misleading exit
  code. Use `--fetch-timeout 600000` and never mask the exit status of a command whose success matters.

## Done when

- `docker compose up` brings up Postgres and a reloading API with no manual steps.
- A fresh clone can go from `.env.example` to a running stack using only the README.
- CI is green on the first commit.
