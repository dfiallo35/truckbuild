# Stage 3 — Marketing pages

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
