# Stage 3 — Marketing pages

> **Status: complete.** Checkpoint verified 2026-08-26.

**Goal:** every public, non-configurator route exists, prerenders, and is indexable.

**Prerequisite:** Stage 2 checkpoint passes.

## Routes

| Route | Contents |
|---|---|
| `/` | Full-bleed hero; the three platform cards with starting price and purpose; a "built for different purposes" grid; process (consult → design → build → deliver); proof (specs, warranty, build time); closing CTA |
| `/builds` | Catalog of all platforms, filterable by purpose |
| `/builds/[slug]` | Platform detail: gallery, spec table, standard equipment, chassis options, starting price, and the primary **"Start Customizing"** CTA into the configurator |
| `/purposes/[slug]` | Vertical landing pages (expedition, service, response) routing visitors to the right platform — these carry the "trucks for different purposes" positioning |
| `/about`, `/process`, `/gallery`, `/contact`, `/legal/privacy` | Supporting pages |

## Steps

1. Build the routes above, using `generateStaticParams` over platform and purpose slugs.
2. **SEO** — per-route `generateMetadata`, Open Graph images, `sitemap.ts`, `robots.ts`, and
   `Product` + `Organization` JSON-LD on platform pages.
3. Wire `/contact` form markup only; its submission lands in [Stage 5](05-quote-pipeline.md).

## Checkpoint

```bash
cd web && pnpm build   # confirm platform/purpose routes are prerendered, not dynamic
```

Then run Lighthouse on `/` and `/builds/bristlecone`: Accessibility and SEO at 95+.

## Done when

- Every route prerenders at build time.
- `sitemap.xml` lists all platform and purpose pages.
- Rich Results Test validates the `Product` JSON-LD.

## Notes from the build

- **`catalog.yaml`'s image paths had no files behind them.** Stage 1/2 seeded `/images/<slug>/*.jpg`
  URLs but nothing under `web/public/` ever produced them, so every `MediaBlock`/`next/image` would
  have 404'd. Generated placeholder cinematic-gradient art per platform (distinct hue/motif per
  vertical) with `rsvg-convert` + ImageMagick and committed it to `web/public/images/` at the exact
  paths the seed already references — no seed or schema change needed. Swapping in real photography
  later is a drop-in file replacement (see docs/decisions.md's accepted risk on photography).
- **Purposes (expedition/service/response) are frontend-only content**, not a backend entity —
  `web/src/lib/purposes.ts` maps each purpose slug to one `platformSlug` and is looked up against the
  live catalog at request time. This keeps `/purposes/[slug]` inside the cache-tag contract without
  adding a table; if purposes ever need to span multiple platforms, that file is the only place to
  change.
- **Per-route dynamic OG images** (`opengraph-image.tsx` under `builds/[slug]` and `purposes/[slug]`)
  pick up their parent route's `generateStaticParams` automatically — no separate `generateImageMetadata`
  needed for a single image per route.
- **The "Start customizing" CTA links to `/configurator/[slug]`**, which doesn't exist until Stage 4.
  Next.js's Link prefetch 404s on it in the console during dev/Lighthouse — expected until that stage
  lands, not a Stage 3 defect.
