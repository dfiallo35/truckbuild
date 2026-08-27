---
name: deploy
description: Deploying TruckBuild, or diagnosing the live site — two Vercel projects (the Next.js app and the FastAPI service) against Neon Postgres. Use this whenever deploying, redeploying, or promoting a change; when adding or changing an environment variable on either service; when a merged change has not appeared on the live site; and when the deployed API is 404ing, 302ing, erroring, or exhausting connections. Deploying no longer runs migrations, and several failure modes here report success while serving nothing, so treat "the deploy succeeded" as the start of the check rather than the end.
---

# Deploying

`docs/deploy.md` is the full runbook. This skill is the part that has to be in your head *before* you
act, because most of what goes wrong here fails silently.

## What is deployed where

| | Project | Root directory | URL |
|---|---|---|---|
| Web | `truckbuild` | `web` | <https://truckbuild.vercel.app> |
| API | `truckbuild-api` | `api` | <https://truckbuild-api.vercel.app> |
| Postgres | Neon `truckbuild` (`blue-cloud-62098029`), `aws-us-west-2` | — | — |

Both projects deploy on push to `main`. Values for every secret are in the gitignored
`.env.production.local` at the repo root.

**`api/render.yaml` and `api/Dockerfile` are dead config.** They describe a container deployment that
is not running, kept as the thing to return to on a paid plan. Do not "fix" a deploy problem by
reaching for them, and do not treat `render.yaml` as a description of what production does.

## The three things that will bite you

### 1. A deploy does not run migrations

The API is a Python function; there is no start hook. **Push a migration-dependent change and the
deploy succeeds while its queries fail.** Migrate by hand, against Neon's *direct* URL, before merging
the code that needs it — and order the change so the gap is survivable. The `alembic-migration` skill
has the expand/deploy/contract table; follow it rather than improvising.

### 2. A Python deploy can succeed while building nothing

`api/vercel.json` must declare `{"framework": "fastapi"}`, and `api/pyproject.toml` must carry
`[tool.vercel] entrypoint = "app.main:app"`. Without the first, Vercel detects the project as "Other",
runs a **Node** build, and reports success in ~50ms having built no function — every route then 404s.

The tell is in the build log:

```
Build Completed in /vercel/output [51ms]
```

No `Using Python`, no `Installing required dependencies from uv.lock` above it. A healthy build says
both. **A green deploy with 404s is this, nearly every time.**

### 3. Deployment Protection answers 302, not 401

Vercel Authentication is on by default for a new project and redirects *every* route to an SSO page,
including the web app's server-side fetches. It does not read as an auth setting; it reads as a broken
API. It must be **off** for `truckbuild-api` (Settings → Deployment Protection). The catalog is public
by design and the admin routes are guarded by `ADMIN_TOKEN` independently.

## Connection strings: two, for different callers

| | Host | Used by |
|---|---|---|
| Pooled | `ep-…**-pooler**.…neon.tech` | The **deployed API**. Frozen function instances hold connections; enough of them against the direct endpoint exhaust the limit |
| Direct | `ep-….…neon.tech` | **Alembic and `app.seed`** — anything that wants a real session |

Both need the `+psycopg` prefix. Plain `postgresql://` fails at startup with a driver error, and that
is the single most common way a first deploy breaks.

## Tooling

Vercel and Neon are both reachable over MCP, and the Vercel CLI is installed and authenticated. The
tools are deferred — load them first:

```
ToolSearch("select:mcp__plugin_vercel_vercel__list_deployments,mcp__plugin_vercel_vercel__get_project,mcp__plugin_vercel_vercel__get_deployment_build_logs")
ToolSearch("select:mcp__plugin_neon_neon__run_sql,mcp__plugin_neon_neon__get_connection_string")
```

Environment variables go through the CLI, from the linked directory (`web/` or `api/`) — there is no
MCP tool for them:

```bash
cd api
printf 'value' | vercel env add NAME production
vercel env ls
```

`vercel env add` fails if the name already exists in that environment; `vercel env rm NAME production
--yes` first. **Changing an env var does not redeploy** — the running deployment keeps its old values
until you `vercel deploy --prod` or push.

> `vercel link` **overwrites** `.env.local` in the directory it runs in, dropping local dev values.
> Put `API_BASE_URL` and `REVALIDATE_SECRET` back afterwards.

## Verifying, every time

"The deploy succeeded" is not evidence. These are:

```bash
curl -s https://truckbuild-api.vercel.app/healthz                                          # {"status":"ok","environment":"production"}
curl -o /dev/null -w '%{http_code}\n' https://truckbuild-api.vercel.app/v1/admin/quotes    # 401
curl -s https://truckbuild.vercel.app/ | grep -oE '\$[0-9,]+' | sort -u                    # prices, from the API

cd web && E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e                               # 43 passed, 7 skipped
```

The first request pays a cold start. One spec timing out on `page.goto` while the rest pass is a boot,
not a regression — re-run it before reporting a failure.

## When something is wrong

| Symptom | Cause |
|---|---|
| Every API route 404s, build took ~50ms | `api/vercel.json` missing or not naming `fastapi` — no function was built |
| Every API route 302s to an SSO page | Vercel Authentication is on for the API project |
| API 500s, driver error | `DATABASE_URL` missing the `+psycopg` prefix |
| API 500s, settings error at startup | `CORS_ORIGINS` is a bare string; it is typed `list[str]` and must be a JSON array |
| Intermittent "too many connections" | The API is on the direct Neon URL instead of the pooled one |
| Queries fail after a merge that deployed cleanly | A migration was never run. Check `alembic current` against production first |
| Merged catalog edit not on the site | `catalog.yaml` is content; no deploy loads it. Re-seed production — see `catalog-change` |
| Catalog right in Neon, stale on the page | `REVALIDATE_SECRET` differs between the two projects, or the seed ran `--no-revalidate` |
| An env var change had no effect | Env vars apply at deploy time. Redeploy |
| Web build fails collecting page data | `API_BASE_URL` wrong, or the API is failing — check the API first |
| Web build fails at framework detection | Root Directory is not set (`web` for the site, `api` for the API) |
| Domain changed but metadata/sitemap did not | `SITE_URL` in `web/src/lib/site.ts` is a **compile-time constant**. Changing the domain is a rebuild, not a redeploy |

## Related

- `alembic-migration` — the production migration procedure, and the ordering that keeps the
  migrate-then-deploy gap survivable
- `catalog-change` — getting a catalog edit from `catalog.yaml` onto the live site
- `cache-and-revalidation` — when the data is right and only the cache disagrees
- `stage-checkpoint` — the CI-equivalent sweep, which runs before any of this
