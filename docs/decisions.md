# Decisions

## Locked in

| Decision | Choice |
|---|---|
| Scope | Marketing pages **and** a working configurator |
| Front end | Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Back end | **FastAPI owns everything, including the catalog** |
| Database | Postgres (Neon), SQLModel + Alembic |
| Hosting | Next.js on Vercel, FastAPI on Fly.io, Postgres on Neon |
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
