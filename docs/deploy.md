# Deploying TruckBuild

Three services, in this order: **Neon** (Postgres), **Render** (the API), **Vercel** (the web app).
The order is not arbitrary — the API needs a database before it can migrate, and the Vercel build reads
the catalog from the API, so a web deploy against a missing API fails outright rather than degrading.

## What this costs: nothing

This is a test deployment of the site, and the stack is picked to be free at that scale rather than to
be what a launched product would run on.

| Service | Tier | Card required | Cost |
|---|---|---|---|
| Neon | Free | No | $0 |
| Render | Free web service | No | $0 |
| Vercel | Hobby | No | $0 |

Two things that come with the price, both of which have a specific day they will start mattering:

- **The Render free instance sleeps** after about fifteen minutes idle and takes the better part of a
  minute to wake. This matters far less here than it would elsewhere: the marketing pages do not read
  the API at request time — catalog reads live inside `use cache` functions and the pages render from
  cache — so a sleeping API is invisible to someone browsing the site. It lands on the first quote
  submission after an idle spell, and on a Vercel build.
- **Vercel Hobby prohibits commercial use.** Fine while this is a test of the page. The day it is
  actually taking leads for a business, Hobby is no longer a legitimate tier and the site needs Pro
  ($20/seat/mo) or a different host. This is a licensing line, not a technical one — nothing will break
  to tell you.

Migrations are the other compromise: Render's pre-deploy command is a paid feature, so `render.yaml`
runs `alembic upgrade head` in the start command instead. A failed migration therefore takes the service
down, where a proper release command would abort the deploy and leave the old version serving. On one
free instance with no concurrent deploys that is acceptable; it is the first thing to fix on a paid plan.

## 0. What you need first

| Thing | Why |
|---|---|
| A Neon project | `DATABASE_URL` |
| A Render account | Hosts the API |
| A Vercel account | Hosts the web app |
| A Resend API key and a verified sender | Lead email. Without it the mailer logs instead of sending |
| A Sentry DSN (optional) | API error tracking. Omit it and structured logs still work |

The production domain appears in more places than is obvious. Before deploying, set `SITE_URL` in
`web/src/lib/site.ts` — it is a compile-time constant feeding `metadataBase`, canonical URLs,
`sitemap.xml`, and JSON-LD, none of which read an environment variable. For a test deployment the
Vercel-assigned `*.vercel.app` URL is fine, but it does have to be set to something real.

## 1. Neon

Create the project and copy the pooled connection string. The API uses psycopg, so the URL needs the
SQLAlchemy driver prefix that Neon does not give you:

```
postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

`postgresql://…` alone fails at startup with a driver error. This is the single most common way a first
deploy breaks.

## 2. The API on Render

`api/render.yaml` is committed. In the Render dashboard: **New → Blueprint**, point it at the repository,
and it reads that file. Render will prompt for every `sync: false` variable rather than taking it from
the file — that is deliberate, so no secret lives in a git diff.

| Variable | Value |
|---|---|
| `DATABASE_URL` | The Neon URL, with `+psycopg` |
| `ADMIN_TOKEN` | `openssl rand -hex 32` |
| `REVALIDATE_SECRET` | `openssl rand -hex 32` — keep it, Vercel needs the identical value |
| `WEB_BASE_URL` | The Vercel URL. Not known until step 3; set a placeholder and correct it |
| `CORS_ORIGINS` | `["https://your-app.vercel.app"]` |
| `RESEND_API_KEY`, `SALES_INBOX`, `MAIL_FROM` | Lead email |
| `SENTRY_DSN` | Optional |

**`CORS_ORIGINS` is JSON, not a comma-separated list.** It is typed `list[str]` in `app/config.py`, and
pydantic-settings parses a list-typed variable as JSON. `CORS_ORIGINS=https://x.vercel.app` fails at
startup; `CORS_ORIGINS=["https://x.vercel.app"]` is correct. The apex and `www.` are different origins.

Then check it came up:

```bash
curl https://truckbuild-api.onrender.com/healthz
```

The first request after a deploy — or after fifteen idle minutes — takes up to a minute. That is the
free tier waking, not a failure.

## 3. The web app on Vercel

Import the repository, then — the setting that matters — **set the project's Root Directory to `web`**.
The repository root has no `package.json`; without this the build fails immediately at framework
detection.

Environment variables, for Production *and* Preview:

| Name | Value | Notes |
|---|---|---|
| `API_BASE_URL` | `https://truckbuild-api.onrender.com` | **Never** prefix `NEXT_PUBLIC_`. The browser must not learn the API origin |
| `REVALIDATE_SECRET` | the same value set on Render | Byte-identical, or revalidation silently stops working |

If the build fails collecting page data, the API was probably asleep. Wake it with a `curl` to
`/healthz` and redeploy.

Once Vercel has assigned a URL, go back and correct the two Render variables that pointed at a
placeholder:

```
WEB_BASE_URL=https://your-app.vercel.app
CORS_ORIGINS=["https://your-app.vercel.app"]
```

## 4. Seed production

The seed is idempotent — upsert by slug — so it is safe to re-run, and it is the same command every
environment uses. Render's free plan has no SSH, so run it from the dashboard's **Shell** tab, or
temporarily as a one-off job:

```bash
python -m app.seed
```

It revalidates the web app's catalog cache on success, which is why it runs after Vercel is up and
`WEB_BASE_URL` points at it. `--no-revalidate` skips that; CI passes it, having no web app to tell.

## 5. Smoke test

Automated, against the real deployment:

```bash
cd web
E2E_BASE_URL=https://your-app.vercel.app pnpm e2e
```

The specs in `e2e/` are read-only and safe to point at a deployment: they cover the catalog rendering,
the configurator, the shared-build URL round trip, the winch/bumper conflict, keyboard operation, WCAG
AA via axe, and the responsive collapse on a phone. The lead-submitting spec does not run against a
non-local target unless `E2E_ALLOW_WRITES=1` says so, because it stores a real row and emails sales.

By hand, the two things the specs cannot check:

1. Submit a quote and confirm it arrives in the sales inbox. Expect the first one to be slow if the API
   has been idle.
2. `curl -H "Authorization: Bearer $ADMIN_TOKEN" https://truckbuild-api.onrender.com/v1/admin/quotes`
   and confirm the stored total matches what the build sheet showed.

## Routine deploys, afterwards

Both services deploy on push to the default branch. A catalog change additionally needs the seed re-run
from the Render shell, to load the new YAML and revalidate the cache — see `.claude/skills/catalog-change`.

## When something is wrong

| Symptom | Cause |
|---|---|
| API will not start, driver error | `DATABASE_URL` missing the `+psycopg` prefix |
| API will not start, settings error | `CORS_ORIGINS` set as a bare string instead of JSON |
| First request hangs ~50s | The free instance was asleep. Not a fault |
| API down after a deploy | A migration failed in the start command; check the Render logs |
| Browser calls to the API blocked | The origin is not in `CORS_ORIGINS`; apex and `www.` differ |
| Catalog edits never reach the site | `REVALIDATE_SECRET` differs between Render and Vercel |
| Vercel build fails at detection | Root Directory is not set to `web` |
| Vercel build fails collecting page data | `API_BASE_URL` is wrong, or the API was asleep — wake it and redeploy |
| Lead email never arrives | `RESEND_API_KEY` unset (the mailer logs instead), or `MAIL_FROM` is not a Resend-verified sender |
| A build URL 404s | The platform slug was renamed. Slugs are public identifiers; renaming one is a breaking change |

## When this stops being a test

The two things to change, in order:

1. **Vercel Hobby → Pro**, the moment the site is commercially in use. A licensing obligation, not a
   technical one.
2. **Render free → paid, or another host**, when a fifty-second cold start on a lead submission becomes
   unacceptable. That also restores a real pre-deploy migration step.

Neon's free tier is fine to stay on considerably longer than either.
