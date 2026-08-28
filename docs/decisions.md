# Decisions

## Locked in

| Decision | Choice |
|---|---|
| Scope | Marketing pages **and** a working configurator |
| Front end | Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Back end | **FastAPI owns everything, including the catalog** |
| Database | Postgres (Neon), SQLModel + Alembic |
| Hosting | Both services on Vercel, Postgres on Neon — all on free tiers, see below |
| Catalog content | Placeholder verticals — invented demo platforms to be replaced with real data |
| Aesthetic | Dark, cinematic, photo-led |

## The one architectural tension, and how it is resolved

FastAPI owning the catalog conflicts with a marketing site's need for fast, prerendered, SEO-indexable
platform pages. Resolving it is the most important structural decision in this project:

- Next.js 16 **Cache Components** (`cacheComponents: true` in `next.config.ts`) let catalog reads sit inside
  `'use cache'` functions tagged with `cacheTag('catalog')` and `cacheTag('platform-<slug>')`. Pages render
  from cache rather than from a live API call, so a slow or down API does not take the marketing site with it.
- When catalog data changes, FastAPI POSTs to a Next.js revalidation webhook, which calls `revalidateTag`.
  Editors get near-immediate updates without the site paying a per-request API cost.
- The seed catalog is committed as a versioned YAML file loaded by a seed command. This keeps the
  reviewable, version-controlled quality of in-repo content while Postgres remains the runtime source of truth.

## Hosting, and why it is all free (Stage 7)

This deployment is **a test of the page rather than a commercial launch**, so the whole stack is on
free tiers and costs nothing. Getting there took three attempts, and the history is worth keeping
because each rejection was for a different reason:

1. **Fly.io** — dropped when Fly ended its free allowance for organizations created after late 2024.
2. **Render** — dropped when it turned out Render could not clone this **private** repository. That
   needs Render's GitHub App installed on the repo *and* the Render account linked to that GitHub
   identity; the second link cannot be made from any API, and the failure reports itself as an
   unfetchable URL, which reads like a syntax error.
3. **Vercel**, for both services — the API as a Python function beside the Next.js app.

`api/render.yaml` and `api/Dockerfile` are **kept, not deleted**. They are a complete description of
the container deployment and the thing to return to on a paid plan; nothing reads them today, and
[deploy.md](deploy.md) says so plainly.

Three liabilities come with the current arrangement, all dated rather than permanent:

- **Vercel Hobby forbids commercial use.** Legitimate while this is a test. The day the site takes real
  leads for a business, Hobby is the wrong tier and nothing technical will break to say so.
- **There is no automatic migration step.** A container could run `alembic upgrade head` on start; a
  Python function has no equivalent hook. Migrations are run by hand against Neon's direct URL,
  *before* deploying code that depends on them. This is the weakest part of the setup: forgetting it
  means a deploy that succeeds while its queries fail.
- **The rate limiter is per-instance.** `app/core/ratelimit.py` keeps counters in process memory,
  and serverless instances do not share state. It still blunts a naive flood, but it is no longer the
  global control it was designed as. The fix is a shared store — Postgres or KV — and it is deferred
  rather than overlooked.

One thing the caching decision above quietly bought: because marketing pages never read the API at
request time, API cold starts are invisible to a browsing visitor. They surface only on a lead
submission after an idle spell, and on a build.

## Observability (Stage 7)

| Concern | Choice |
|---|---|
| Page analytics | `@vercel/analytics` and `@vercel/speed-insights` — first-party on Vercel, so no third-party host sees the visitor and no cookie banner is owed |
| API errors | Sentry, active only when `SENTRY_DSN` is set, over an always-on layer of structured per-request JSON logs |
| Web errors | Next's `onRequestError` hook server-side, `global-error.tsx` → `/api/client-error` client-side. No error SDK is shipped to the browser |
| Correlation | One `X-Request-ID` per request, forwarded across the service boundary and returned to the caller |

Two decisions inside that are worth stating plainly, because the cheaper version of each looks the same
until it matters:

- **Structured logs are the floor, not the fallback.** They cost nothing, belong to no vendor, and keep
  working when Sentry is off, misconfigured, or rate-limited — which includes every environment except
  production. Sentry is the layer on top, not the thing being relied on.
- **The browser gets no error tracker.** A marketing site should not ship one to every visitor to catch a
  rare failure, so the client reports its crashes to a first-party route instead. That route is
  necessarily unauthenticated — it is called by a page that has just crashed — so it caps the body,
  keeps only known fields, and answers 204 to everything.
- **Lead data never reaches Sentry.** A quote body carries a name, an email, and a phone number. The
  `before_send` scrubber drops the request body, cookies, and credential headers, and it is the most
  heavily tested part of `telemetry.py` because a mistake in it is invisible until after it has shipped.

## Accepted risks

- **The pricing mirror is real duplication.** `price_build` exists in Python (authoritative) and TypeScript
  (instant UI feedback). Accepted deliberately for the UX win and contained by shared test fixtures. If it
  drifts despite that, the fallback is a debounced `POST /v1/price` call instead of mirroring.
- **Admin auth is a bearer token.** Deliberately minimal. The upgrade path is real user accounts once more
  than a couple of people need access.
- **Photography is the critical path for the aesthetic.** The reference site works because the imagery
  carries it. A dark cinematic layout with weak photos reads worse than a plain one — treat swapping in real
  vehicle photography as scheduled work, not an afterthought.

## Explicitly deferred

User accounts and saved builds, financing calculators, dealer/inventory management, real-time build-slot
availability, a 3D/WebGL viewer, i18n, and a CMS. The catalog seed file plus the revalidation webhook is the
seam a CMS would later plug into.
