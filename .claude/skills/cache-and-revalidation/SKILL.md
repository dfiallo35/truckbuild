---
name: cache-and-revalidation
description: TruckBuild's caching contract — catalog reads live inside 'use cache' functions tagged catalog and platform-<slug>, and FastAPI revalidates those tags over a shared-secret webhook. Use this whenever adding or changing a page, layout, route handler, or any function in web/src/ that reads catalog data, whenever touching next.config.ts, the /api/revalidate route, or app/modules/catalog/infrastructure/webhook/revalidate.py, and whenever a catalog edit is correct in Postgres but the site still shows the old value, a page unexpectedly renders dynamically, or a build stops reporting Cache Components as enabled. This caching layer is the resolution to the project's central architectural tension, so breaking it quietly breaks the premise of the whole front end.
---

# Caching and revalidation

## The tension this resolves

FastAPI owns the catalog. A marketing site needs pages that prerender, index well, and stay up when the
API does not. Those two facts pull against each other, and `docs/decisions.md` calls resolving them the
most important structural decision in the project.

The resolution: catalog reads sit inside `'use cache'` functions tagged by scope. Pages render from
cache rather than from a live API call, so a slow or down API costs nothing per request and does not
take the marketing site down with it. When catalog rows change, FastAPI pushes a revalidation webhook
so editors still get near-immediate updates.

Every part of that sentence is load-bearing. A catalog read that escapes the cache turns a prerendered
page into a per-request API dependency, which is the exact failure mode the design exists to avoid.

## The contract

**`cacheComponents: true` in `web/next.config.ts`.** This is Next.js 16 Cache Components (PPR).
Everything below assumes it. `pnpm build` output includes `- Cache Components enabled`; if that line
disappears, the config is not being picked up and every caching assumption here is void. Treat its
absence as a build failure, not a cosmetic change.

**Catalog reads are wrapped, never inline.** They belong in `'use cache'` functions in `web/src/lib/`,
with `cacheLife('hours')` and a tag. No page component calls the API directly — no page component
should know the API exists at all.

**Tags are scoped in two tiers:**

| Tag | Covers | Revalidate when |
|---|---|---|
| `catalog` | Anything listing or spanning platforms — home, `/builds`, purpose pages, sitemap | Any catalog row changes |
| `platform-<slug>` | One platform's detail and configurator data | That platform, its groups, options, or rules change |

Tag at the narrowest scope that is still correct. A change to one option should not blow away the
whole catalog cache, but a change that affects a listing must invalidate `catalog` too.

**`API_BASE_URL` is server-side only.** It must never be prefixed `NEXT_PUBLIC_`. The browser reaches
FastAPI only through Server Actions and route handlers, so the API origin never ships to the client.

**Every response is parsed with Zod in `web/src/lib/api.ts`.** Caching a response that was cast rather
than parsed means caching a shape you never verified — the error then surfaces later, somewhere else,
as an `undefined` with no trail back to the cause.

## The revalidation webhook

`api/app/modules/catalog/infrastructure/webhook/revalidate.py` POSTs `{tags: [...]}` to the web
app's `/api/revalidate` with the shared `REVALIDATE_SECRET`. The route verifies the secret and calls
`revalidateTag` for each tag.

It is the one adapter behind `ICacheInvalidator` (`catalog/domain/interfaces.py`). Callers depend on
the port: `RevalidateCatalogUseCase` in `catalog/application/use_cases.py` decides *which* tags —
including the "none named means every tag the catalog touches" default — and `admin`'s
`POST /v1/admin/revalidate` calls it through `CatalogService`. The tag vocabulary itself
(`CATALOG_TAG`, `platform_tag`, `tags_for_platforms`) lives in `catalog/domain/cache_tags.py`.

Two things about this are easy to get wrong:

- **The secret must match on both sides.** `REVALIDATE_SECRET` is set for the API and for the web app
  independently. When they disagree there is no loud failure — catalog edits simply stop reaching the
  site. If edits are landing in Postgres and not appearing publicly, check this before anything else.
- **A wrong or missing secret must be rejected**, not merely logged. The route is a public endpoint
  that busts caches; leaving it open invites trivial cache-stampede abuse.

Mail delivery is allowed to fail without failing a request, because the lead is already saved.
Revalidation is different: if it fails, log it loudly. Stale catalog data is a wrong price on a public
page, and nothing downstream will notice on its own.

## Finding catalog reads that escaped the cache

The rule "no page component calls the API directly" is a statement about call paths, which is exactly
what the CodeGraph index at `.codegraph/` answers and what grep cannot:

```bash
codegraph explore "what calls the catalog fetch functions in web/src/lib/api.ts"
codegraph explore "cacheTag"     # every tagged read, and the pages reaching each one
```

A page that shows up as a caller of an API function without a `'use cache'` wrapper in between is the
bug — the same one that turns up later in a build as a route that went dynamic. Check this before
adding a cache tag, not after.

## Diagnosing "the site is showing the old value"

Work down the chain rather than guessing:

1. Does `GET /v1/catalog` return the new value? If not, this is a catalog or seed problem — use the
   `catalog-change` skill.
2. Did the API actually send a revalidation, and did it get a 2xx? A 401 here means the secrets differ.
3. Was the *right* tag sent? A platform-scoped revalidation will not refresh the home page listing.
4. Does `pnpm build` still report Cache Components enabled?

## Next.js API details

For the current semantics of `'use cache'`, `cacheLife`, `cacheTag`, `revalidateTag`, and how PPR
decides what prerenders, load the `vercel:next-cache-components` skill or look the API up with
context7 rather than working from memory. This file describes the project's contract; that one
describes the framework, and the framework moves faster than this document does.

## Related

`catalog-change` — the upstream chain that produces the data being cached.
`stage-checkpoint` — Stage 2 and 3 checkpoints both verify prerendering behavior.
