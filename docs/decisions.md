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
| API structure | Modular monolith — feature modules, four layers each, over a shared `core` |

### API structure

The layout is adapted from [`dfiallo35/property-management`](https://github.com/dfiallo35/property-management),
which runs the same vertical-slice-over-a-shared-`core` shape across fourteen features. Three
choices inside it are worth recording, because none is obvious from reading the code cold:

- **Entities are separate from tables.** Pure pydantic in `domain/models.py`, SQLModel in
  `infrastructure/postgres/tables.py`, a mapper in each direction. It costs roughly 150 lines of
  mapper code across the two catalog mappers and one more place to add a field. It buys a
  `domain/` that imports no ORM — enforced by the `Domain forbids persistence` import-linter
  contract, not by review — and lets `price_build` and `validate_selection` take real entities
  instead of shim types.
- **The kernel carries the whole CRUD set.** `BaseUseCase` plus `Create`/`Update`/`Delete`/`List`/
  `Paginate`/`GetById`/`BatchUpdate`, even though this service leaves several of them with no
  caller — the catalog is seeded rather than edited over HTTP, and a lead is never mutated once
  submitted. Carried whole because the set is easier to reason about than an à la carte subset,
  and marked `# pragma: no cover` where unreached rather than quietly dragging the coverage
  number down.
- **The seed writes through the repository, not around it.** `IPlatformRepository.
  upsert_from_catalog` is a bulk, catalog-shaped write — not the generic single-entity `create`/
  `update` the kernel's CRUD use cases call. `PlatformMapper.to_table` stays the deliberately
  unimplemented dead end it always was (the catalog has no HTTP write path), so `UpdateUseCase`,
  `DeleteUseCase` and `BatchUpdateUseCase` still have few or no callers in this service — carried
  for the same reason as the rest of the CRUD set, not because stage 13 found a use for them.

Deviations from the reference — FastAPI `Depends` rather than `dependency_injector`, sync rather
than async, `limit`/`offset` rather than `page`/`size`, SQLModel tables rather than plain
SQLAlchemy, no i18n — are each named and justified in
[stages/09-core-kernel.md](stages/09-core-kernel.md#deviations-from-the-reference-and-why).

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
- **The rate limiter is per-instance.** `app/core/infrastructure/ratelimit.py` keeps counters in
  process memory, and serverless instances do not share state. It still blunts a naive flood, but it is no longer the
  global control it was designed as. The fix is a shared store — Postgres or KV — and it is deferred
  rather than overlooked. Stage 11 did not fix it, but it made the fix a one-file change: the
  limiter is now injected through `quotes/dependencies.py` behind `IRateLimiter`, so a shared
  implementation swaps in without anything above it changing.

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
- **A visitor with no WebGL gets no build view.** The 2D layer composite that used to cover this case is
  gone as of Stage 17. `platform.hero_image` serves as the `<canvas>`'s poster while the GLB streams in
  *and* as the terminal state when WebGL is unavailable or the model fails to load, with one line of
  explanation — a static image that does not react to option toggles. Chosen deliberately over
  maintaining two build views; see the Stage 16 page of the
  [archived development plan](https://app.notion.com/p/3ce774db73568150bcd2cb9e6b099239)'s "The
  no-WebGL position, stated plainly" for the reasoning and its stated recovery path.

## The 3D build view (Stages 14–17)

What replaced the deferred "3D/WebGL viewer" below: Postgres holds a `BuildModel` reference — a URL,
a content hash, and a size — while the GLB bytes themselves live in Vercel Blob. The split exists
because **a Vercel function caps request bodies at 4.5 MB** and these models run 5–50 MB, which rules
out an upload endpoint outright; the bytes reach Blob through `python -m app.assets sync`, run by an
operator, never through a request. Blob paths are content-addressed (the hash is part of the path),
which is what makes `cacheControlMaxAge: immutable` safe on them. The configurator's
`/configurator/[slug]` renders that model in WebGL via a lazily loaded three.js chunk; there is no
layer-composite fallback any more (see the accepted risk above).

## Explicitly deferred

User accounts and saved builds, financing calculators, dealer/inventory management, real-time build-slot
availability, i18n, and a CMS. The catalog seed file plus the revalidation webhook is the seam a CMS
would later plug into.
