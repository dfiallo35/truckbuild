# Architecture

How TruckBuild is put together, and why it is put together that way. For the choices themselves and
the ones deliberately rejected, see [decisions.md](decisions.md); for the vocabulary, see
[domain-model.md](domain-model.md).

## The shape of it

Two services, no monorepo tooling tying them together. Each is installed, run, tested, and deployed
from its own directory.

| | `web/` | `api/` |
|---|---|---|
| Stack | Next.js 16 (App Router), TypeScript, Tailwind 4 | FastAPI, SQLModel, Alembic |
| Package manager | pnpm | uv |
| Owns | Presentation, the configurator UI, lead forms | The catalog, authoritative pricing, quotes, admin |
| Talks to | The API, server-side only | Postgres, and the web app's revalidation hook |

```mermaid
flowchart LR
    V["Visitor's browser"]
    subgraph W["web/ — Next.js on Vercel"]
        P["Pages<br/>(prerendered)"]
        C["'use cache' catalog reads<br/>tagged catalog / platform-slug"]
        SA["Server Actions<br/>+ route handlers"]
        RV["/api/revalidate"]
    end
    subgraph A["api/ — FastAPI on Vercel"]
        R["Routers<br/>/v1/catalog · /v1/quotes · /v1/admin"]
        S["Pure services<br/>pricing.py · rules.py"]
    end
    DB[("Postgres<br/>Neon")]

    V --> P
    P --> C
    C -- "build time / cache miss" --> R
    V -- "form submit" --> SA
    SA --> R
    R --> S
    R --> DB
    R -- "catalog changed<br/>REVALIDATE_SECRET" --> RV
    RV -. "revalidateTag" .-> C
```

The dotted line is the important one. Pages do not call the API per request; they read from cache,
and the API pushes an invalidation when the underlying rows change.

## The central tension, and how it is resolved

FastAPI owning the catalog conflicts with a marketing site's need for fast, prerendered,
SEO-indexable pages. Nearly every structural decision below falls out of resolving that.

**Next.js 16 Cache Components.** `cacheComponents: true` in `web/next.config.ts` enables partial
prerendering, and every catalog read lives inside a `'use cache'` function in
`web/src/lib/catalog.ts`:

```ts
export async function getCatalog(): Promise<Catalog> {
  "use cache";
  cacheLife("hours");
  cacheTag("catalog");
  return fetchCatalog();
}
```

Pages render from that cache rather than from a live call, which buys three things at once: pages are
fast, they are indexable, and **a slow or down API does not take the marketing site with it**.

> If `pnpm build` stops printing `- Cache Components enabled`, every assumption on this page is void.
> That line is the check, not the config file.

**Invalidation, not expiry.** When catalog rows change, FastAPI POSTs to the web app's
`/api/revalidate` with a shared `REVALIDATE_SECRET`; the route calls `revalidateTag`. Editors get
near-immediate updates without the site paying a per-request API cost. The tags are `catalog` and
`platform-<slug>`, so a single platform edit does not evict everything.

**YAML as versioned content, Postgres as runtime truth.** `api/seed/catalog.yaml` is the reviewable,
version-controlled source; `app/seed.py` upserts it by slug, so re-running is always safe. Postgres
remains what the API reads. This is also the seam a CMS would later plug into.

## Boundaries that must hold

These are load-bearing. Breaking one does not fail loudly.

**`catalog/domain/pricing.py` and `catalog/domain/rules.py` are pure** — no `fastapi`, no
`sqlmodel` imports. That purity is what makes them cheap to test without a database and safe to
mirror on the client. Both are written test-first, and the rule is now checked by the
`Pricing mirror purity` import contract rather than trusted to a docstring.

**The pricing mirror is deliberate duplication.** `price_build` exists twice: Python
(`api/app/modules/catalog/domain/pricing.py`, authoritative) and TypeScript (`web/src/lib/pricing.ts`, for instant
UI feedback as a visitor clicks). Same for `validate_selection` / `rules.ts`. The only thing keeping
them from drifting is that **both are tested against a single shared JSON fixture** consumed by
pytest and Vitest — add a case on one side and the other side fails.

**The server price is authoritative.** `POST /v1/quotes` re-validates the selection and recomputes the
total from the database, ignoring any client-supplied price. The mirror is a UX affordance; it is
never trusted.

**The browser never sees the API origin.** `API_BASE_URL` is server-side only and must never be
prefixed `NEXT_PUBLIC_`. The browser reaches FastAPI exclusively through Server Actions and route
handlers.

**Every backend response is parsed with Zod**, in `web/src/lib/api.ts`, rather than cast. A backend
shape change surfaces as a named field error at the boundary instead of a runtime `undefined` three
components deep.

**Every environment variable is declared in `app/config.py`** (pydantic-settings), so a missing or
malformed value fails at startup rather than deep inside a request.

**Slugs are public identifiers.** They appear in URLs and in shared build links. Renaming one is a
breaking change.

## Build state lives in the URL

A build is a platform plus a set of selected option slugs, encoded in the query string as
`?o=slug-a,slug-b`. `web/src/lib/build.ts` owns the encoding.

That choice gives shareable, refresh-safe, back-button-correct builds with no database round trip and
no session. The cost is that the query string is untrusted input, so **decoding repairs rather than
throws** — a shared URL outlives the catalog it was built from:

| The URL says | `decodeSelection` does |
|---|---|
| An option that no longer exists | Drops it |
| Two options from a `single`-select group | Keeps the first named |
| Nothing for a `required` group | Falls back to that group's first option |
| A combination that violates a rule | **Keeps it** |

That last row is the interesting one. A conflicting selection is preserved on purpose, because the
configurator can explain a conflict inline — and cannot explain a choice it silently discarded.

The URL is written with `history.replaceState`, not a router navigation, so configuring does not push
a history entry per click.

## Route groups

Marketing pages live under `web/src/app/(site)/`, whose layout carries `Header` and `Footer`. The root
layout holds only the document shell.

`/configurator/[slug]` sits **outside** that group deliberately: it is full-bleed with its own minimal
bar, and a nested layout cannot remove a parent's chrome. Route groups add no URL segment, so paths
are unaffected.

## The request path for a lead

The one flow that crosses every boundary:

1. The visitor configures a build; `pricing.ts` updates the total on each click, locally.
2. They submit the form. A **Server Action** (`web/src/lib/actions.ts`) receives it — the browser
   never learns the API origin.
3. The action forwards to `POST /v1/quotes`, passing the visitor's `x-forwarded-for` so rate limiting
   buckets by visitor rather than putting every submission in the world in one bucket.
4. FastAPI re-validates: unknown slugs, single-select groups with two choices, required groups with
   none, and every `requires`/`excludes` rule.
5. It **recomputes the price** from the database and stores that, not what the client sent.
6. It generates a reference (`TB-XXXXXX`), retrying on the unique-index collision rather than hoping.
7. The mailer notifies sales — or logs, when `RESEND_API_KEY` is unset.
8. The visitor lands on `/thank-you` with the reference number.

Rejections all come back in one error shape (`api/app/errors.py`), FastAPI's own 422 included, so the
web app has a single body to parse and render beside the field at fault.

## Observability

| Concern | Mechanism |
|---|---|
| Page analytics | `@vercel/analytics` + `@vercel/speed-insights` — first-party, so no third party sees the visitor |
| API errors | Sentry, active only when `SENTRY_DSN` is set, layered over always-on structured JSON request logs |
| Web errors | `onRequestError` server-side; `global-error.tsx` → `/api/client-error` client-side |
| Correlation | One `X-Request-ID` per request, forwarded across the service hop and returned to the caller |

Two points worth stating, because the cheaper version of each looks identical until it matters:

- **Structured logs are the floor, not the fallback.** They cost nothing, belong to no vendor, and
  keep working when Sentry is off, misconfigured, or rate-limited — which is every environment except
  production. Sentry is the layer on top.
- **Lead data never reaches Sentry.** A quote body carries a name, an email, and a phone number. The
  `before_send` scrubber in `telemetry.py` drops the request body, cookies, and credential headers,
  and it is the most heavily tested code in that module, because a mistake in it is invisible until
  after it has shipped.

Middleware order in `app/main.py` is load-bearing and counter-intuitive: `add_middleware` inserts at
position 0 and the stack is built by wrapping in reverse, so **the last one added is the outermost**.
Telemetry is added last so it stamps the request id before anything else can fail.

## Security posture

- **Admin is a single bearer token**, compared with `compare_digest`. Deliberately minimal for two or
  three people reading leads; the upgrade path is real accounts. The guard is on the *router*, so a
  route added there is protected by construction rather than by the author remembering.
- **Lead forms** carry a honeypot field, a minimum time-to-submit, and a per-IP rate limit. All three
  are tuned generously: turning away a real customer costs more than storing a junk lead.
- **`/api/client-error`** is necessarily unauthenticated — it is called by a page that has just
  crashed — so it caps the body, keeps only known fields, and answers 204 to everything.
- **Security headers** are set in `next.config.ts`: `nosniff`, `X-Frame-Options: DENY`,
  `frame-ancestors 'none'`, a referrer policy that does not leak a configured build to outbound links,
  a `Permissions-Policy` denying everything unused, and HSTS.

## Where things live

```
api/
  app/
    main.py             composition root — mounts each module's router
    seed.py             catalog.yaml → Postgres
    core/               shared by every module, imports none of them
      config.py         every env var declared      db.py         engine & session
      errors.py         the one error envelope      telemetry.py  request logs & Sentry
      ratelimit.py      in-process window           revalidate.py cache-tag webhook
    modules/
      catalog/          platforms · option groups · options · rules · assets
        domain/         entities/ · enums.py · pricing.py · rules.py
                        ↑ pricing and rules are pure, mirrored, test-first
        application/    infrastructure/             (stages 9–12 fill these)
        presentation/   router.py · schemas.py
      quotes/           lead submission, priced by the server
        domain/         entities/ · enums.py · refs.py · spam.py
        application/    infrastructure/mail.py
        presentation/   router.py · schemas.py
      admin/            guarded reads over quotes and catalog — owns no tables,
        application/    so it carries no domain and no infrastructure
        presentation/   router.py · schemas.py
  seed/catalog.yaml   versioned catalog content
  alembic/            migrations

web/src/
  app/(site)/         marketing pages, with Header + Footer
  app/configurator/   full-bleed, outside the (site) group
  app/api/            revalidate · client-error
  components/         configurator/ · leads/ · shared
  lib/
    api.ts       Zod-parsed API client        catalog.ts  'use cache' reads
    build.ts     URL build encoding           pricing.ts  ← mirrors pricing.py
    rules.ts     ← mirrors rules.py           actions.ts  Server Actions
    purposes.ts  editorial verticals          site.ts     SITE_URL, nav, footer
```

`purposes.ts` is worth a note: purpose verticals (Expedition, Service, Response) are **editorial
framing over the catalog, not a backend entity**. Each names a `platformSlug` looked up from FastAPI
at request time. One purpose maps to one platform today; the model allows more without a page rewrite.
