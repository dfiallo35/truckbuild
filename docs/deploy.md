# Deploying TruckBuild

Three pieces, in this order: **Neon** (Postgres), the **API on Vercel**, the **web app on Vercel**.
The order is not arbitrary — the API needs a migrated database before it can serve anything, and the
web build reads the catalog from the API at build time, so a web deploy against a missing API fails
outright rather than degrading.

Two separate Vercel projects, not one:

| Project | Root directory | Serves |
|---|---|---|
| `truckbuild-api` | `api` | FastAPI, as a Python function |
| `truckbuild` | `web` | Next.js |

## Why not Render

`api/render.yaml` is still in the repository and is **no longer the deployed configuration**. It is kept
because it is a complete, working description of the container deployment and is the thing to return to
on a paid plan — but nothing reads it today.

Render was the original choice and could not clone this repository. Render fetches a *public* repo with
no setup, but a **private** one requires both its GitHub App installed on the repo *and* the Render
account linked to that GitHub identity. Signing up with email or Google leaves the second link unset,
and the API then reports:

```
400: passed in repository URL is invalid or unfetchable:
     https://github.com/dfiallo35/truckbuild
```

That message lists accepted URL formats, so it reads as a syntax error when the URL is already correct.
It means Render cannot see the repository. Nothing in Render's API or MCP tooling can grant that access.

## What this costs: nothing

A test deployment of the site, on tiers picked to be free at that scale rather than to be what a launched
product would run on.

| Service | Tier | Card required | Cost |
|---|---|---|---|
| Neon | Free | No | $0 |
| Vercel (both projects) | Hobby | No | $0 |

**Vercel Hobby prohibits commercial use.** Fine while this is a test of the page. The day it is actually
taking leads for a business, Hobby is no longer a legitimate tier and the site needs Pro ($20/seat/mo).
This is a licensing line, not a technical one — nothing will break to tell you.

## The two costs of running the API serverless

Both are consequences of moving off a container, and both are worth knowing before they surprise someone:

- **There is no automatic migration step.** The container ran `alembic upgrade head` in its start
  command; a Python function has no equivalent hook. Migrations are now run by hand, from a machine with
  the **direct** Neon URL, *before* deploying code that depends on them. Forgetting this is the way to
  break production: the deploy succeeds and the queries fail.
- **`app/core/infrastructure/ratelimit.py` keeps its counters in memory.** On a container that is a
  single shared process. On serverless, instances come and go and do not share state, so the lead-form
  rate limit is enforced per instance rather than globally — it still blunts a naive flood, but it is
  not the control it was. `QUOTE_MIN_SUBMIT_MS` and the honeypot in
  `app/modules/quotes/domain/spam.py` are unaffected. Fixing it properly means moving the counter into
  Postgres or a KV store.

## 0. What you need first

| Thing | Why |
|---|---|
| A Neon project | `DATABASE_URL` |
| A Vercel account | Hosts both projects |
| A Resend API key and a verified sender | Lead email. Without it the mailer logs instead of sending |
| A Sentry DSN (optional) | API error tracking. Omit it and structured logs still work |

The production domain appears in more places than is obvious. Before deploying the web app, set
`SITE_URL` in `web/src/lib/site.ts` — it is a compile-time constant feeding `metadataBase`, canonical
URLs, `sitemap.xml`, and JSON-LD, none of which read an environment variable. Changing the domain is a
rebuild, not a redeploy.

## 1. Neon

Create the project. You need **both** connection strings, and they are used for different things:

| | Host | Used by |
|---|---|---|
| Direct | `ep-….<region>.aws.neon.tech` | Alembic, `app.seed` — anything wanting a real session |
| Pooled | `ep-…-pooler.<region>.aws.neon.tech` | The deployed API |

The API uses psycopg, so both need the SQLAlchemy driver prefix that Neon does not give you:

```
postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

`postgresql://…` alone fails at startup with a driver error. This is the single most common way a first
deploy breaks.

**The deployed API must use the pooled URL.** An idle serverless instance is frozen rather than torn
down, so it holds its connections; enough concurrent instances against the direct endpoint exhaust
Neon's connection limit. PgBouncer in front makes that a non-issue.

Then migrate and seed, from your machine, using the **direct** URL:

```bash
cd api
export DATABASE_URL='postgresql+psycopg://…@ep-….aws.neon.tech/truckbuild?sslmode=require'
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
```

`--no-revalidate` because there is no web app to notify yet. The seed upserts by slug, so re-running is
always safe.

## 2. The API on Vercel

Root Directory **`api`**. Two files make this work, both committed:

- `api/vercel.json` — `{"framework": "fastapi"}`. **Without this the deploy silently does nothing.**
  Vercel detects the project as "Other", runs a Node build, finishes in ~50ms having built no function,
  and every route returns 404. The build log saying `Build Completed in /vercel/output [51ms]` with no
  install step is the tell.
- `api/pyproject.toml` — `[tool.vercel] entrypoint = "app.main:app"`. Vercel otherwise looks for `app`
  in a conventional entrypoint file (`index.py`, `main.py`) and finds nothing.

Dependencies install from `uv.lock`, and `.python-version` pins 3.13. `api/.vercelignore` keeps tests,
the virtualenv, and the Dockerfile out of the bundle.

Environment variables, on Production *and* Preview:

| Variable | Value |
|---|---|
| `DATABASE_URL` | The **pooled** Neon URL, with `+psycopg` |
| `ADMIN_TOKEN` | `python -c 'import secrets; print(secrets.token_urlsafe(32))'` |
| `REVALIDATE_SECRET` | Same generator — keep it, the web project needs the identical value |
| `ENVIRONMENT` | `production` |
| `WEB_BASE_URL` | The web app's URL. Not known until step 3; set a placeholder and correct it |
| `CORS_ORIGINS` | `["https://truckbuild.vercel.app"]` |
| `RESEND_API_KEY`, `SALES_INBOX`, `MAIL_FROM` | Lead email |
| `SENTRY_DSN` | Optional |

**`CORS_ORIGINS` is JSON, not a comma-separated list.** It is typed `list[str]` in `app/config.py`, and
pydantic-settings parses a list-typed variable as JSON. `CORS_ORIGINS=https://x.vercel.app` fails at
startup; `CORS_ORIGINS=["https://x.vercel.app"]` is correct. The apex and `www.` are different origins.

**Turn Vercel Authentication off for this project** (Settings → Deployment Protection). It is on by
default and makes every route answer `302` to an SSO page — including the web app's server-side fetches,
which is not an error anyone reads as "protection is on". The catalog is public data by design, and the
admin routes are guarded by `ADMIN_TOKEN` independently.

Then check it came up:

```bash
curl https://truckbuild-api.vercel.app/healthz
curl -o /dev/null -w '%{http_code}\n' https://truckbuild-api.vercel.app/v1/admin/quotes   # expect 401
```

## 2.5. Vercel Blob, for model GLBs

Stage 15 gives the API a second place it writes to: model GLBs (5–50 MB each) go to Vercel Blob, not
through the API itself — a Vercel function caps a request body at 4.5 MB, so there is deliberately no
upload endpoint. `python -m app.assets sync` PUTs straight from an operator's machine to
`blob.vercel-storage.com`, and only the resulting URL, content hash and byte size land in Postgres.

From the API project's dashboard: **Storage → Create Database → Blob**, then connect it to the
`truckbuild-api` project — this sets `BLOB_READ_WRITE_TOKEN` on it automatically. Copy that same value
into your own shell before running a sync from an operator machine; `app/assets.py` selects
`VercelBlobStore` whenever it is set and falls back to writing under `web/public/models/` when it is not,
which is what docker compose, CI and the test suite use.

```bash
cd api
export DATABASE_URL='postgresql+psycopg://…@ep-….aws.neon.tech/truckbuild?sslmode=require'
export BLOB_READ_WRITE_TOKEN='vercel_blob_rw_…'
uv run python -m app.assets sync --dry-run   # reports what would upload, writes nothing
uv run python -m app.assets sync
```

Put the `.glb` files at `api/seed/models/<platform-slug>.glb` first — gitignored, since these are large
binaries and `seed/catalog.yaml` stays the reviewable text half of the seed. A re-run only uploads a
platform whose file's sha256 has changed since the last sync; everything else is reported `unchanged`.

## 3. The web app on Vercel

Import the repository, then — the setting that matters — **set Root Directory to `web`**. The repository
root has no `package.json`; without this the build fails immediately at framework detection.

Environment variables, for Production *and* Preview:

| Name | Value | Notes |
|---|---|---|
| `API_BASE_URL` | `https://truckbuild-api.vercel.app` | **Never** prefix `NEXT_PUBLIC_`. The browser must not learn the API origin |
| `REVALIDATE_SECRET` | the same value set on the API project | Byte-identical, or revalidation silently stops working |

Once Vercel has assigned a URL, go back and correct the two API variables that pointed at a placeholder,
then redeploy the API so it picks them up:

```
WEB_BASE_URL=https://truckbuild.vercel.app
CORS_ORIGINS=["https://truckbuild.vercel.app"]
```

## 4. Smoke test

Automated, against the real deployment:

```bash
cd web
E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e
```

The specs in `e2e/` are read-only and safe to point at a deployment: they cover the catalog rendering,
the configurator, the shared-build URL round trip, the winch/bumper conflict, keyboard operation, WCAG
AA via axe, and the responsive collapse on a phone. The lead-submitting spec does not run against a
non-local target unless `E2E_ALLOW_WRITES=1` says so, because it stores a real row and emails sales.

By hand, the two things the specs cannot check:

1. Submit a quote and confirm it arrives in the sales inbox.
2. `curl -H "Authorization: Bearer $ADMIN_TOKEN" https://truckbuild-api.vercel.app/v1/admin/quotes`
   and confirm the stored total matches what the build sheet showed.

## Routine deploys, afterwards

Both projects deploy on push to `main`. A catalog change additionally needs the seed re-run from your
machine against the direct Neon URL — without `--no-revalidate` this time, so it busts the web app's
cache tags. See `.claude/skills/catalog-change`.

**A migration is not part of a deploy.** Run `alembic upgrade head` against the direct URL *before*
pushing code that needs it.

**Neither is a model change.** A new or updated GLB is `python -m app.assets sync` run from an operator
machine, alongside the seed and the migration — see "Vercel Blob, for model GLBs" above.

## When something is wrong

| Symptom | Cause |
|---|---|
| Every route 404s, build took ~50ms | `api/vercel.json` missing or not naming `fastapi` — no function was built |
| Every route 302s to an SSO page | Vercel Authentication is on for the API project |
| API will not start, driver error | `DATABASE_URL` missing the `+psycopg` prefix |
| API will not start, settings error | `CORS_ORIGINS` set as a bare string instead of JSON |
| Intermittent "too many connections" | The API is on the direct Neon URL instead of the pooled one |
| Queries fail on a fresh deploy | A migration was never run — deploys do not run them |
| Browser calls to the API blocked | The origin is not in `CORS_ORIGINS`; apex and `www.` differ |
| Catalog edits never reach the site | `REVALIDATE_SECRET` differs between the two projects |
| Vercel build fails at detection | Root Directory is not set (`web` for the site, `api` for the API) |
| Vercel build fails collecting page data | `API_BASE_URL` is wrong, or the API is failing |
| Lead email never arrives | `RESEND_API_KEY` unset (the mailer logs instead), or `MAIL_FROM` is not a Resend-verified sender |
| A build URL 404s | The platform slug was renamed. Slugs are public identifiers; renaming one is a breaking change |

## When this stops being a test

In order:

1. **Vercel Hobby → Pro**, the moment the site is commercially in use. A licensing obligation, not a
   technical one.
2. **Move the rate limiter out of process memory**, since serverless makes it per-instance.
3. **Restore a real migration step**, either by going back to the container deployment `render.yaml`
   describes, or by running migrations from CI on merge.

Neon's free tier is fine to stay on considerably longer than any of these.
