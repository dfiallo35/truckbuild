# Stage 2 — Design system and app shell

> **Status: complete.** Checkpoint verified 2026-08-26.

**Goal:** the dark, cinematic visual direction exists as tokens, the shell is built, and the front end can
read the catalog through a typed, cached client.

**Prerequisite:** Stage 1 checkpoint passes — the front end needs real data to build against.

> **Load the `frontend-design` skill at the start of this stage.** The visual direction *is* the product
> here, and framework defaults will read as templated.

## Steps

1. **Tokens before pages.** A near-black canvas, a single high-contrast accent, condensed display type for
   headings against a neutral grotesk for body, and generous vertical rhythm so full-bleed photography can
   breathe. Define them as CSS custom properties in `globals.css` and map them into the Tailwind theme, so
   no component ever hardcodes a color.
2. **App shell** — a header that is transparent over hero imagery and gains a background on scroll, a
   persistent "Talk to Sales" CTA, mobile navigation, and a footer.
3. **Shared primitives** — `PlatformCard`, `SpecList`, `SectionHeading`, `MediaBlock`, `PriceTag`,
   `CTAButton`. Build these once here rather than discovering them five times in Stage 3.
4. **Typed API client** — `web/src/lib/api.ts` with Zod schemas parsing every backend response. Parsing at
   the boundary rather than casting means a backend shape change surfaces as a clear error instead of a
   runtime `undefined` deep inside a component.
5. **Cached catalog reads** — wrap them in `'use cache'` functions with `cacheLife('hours')` and
   `cacheTag('catalog')` / `cacheTag('platform-<slug>')`.

## Checkpoint

- The shell renders using only tokens; grepping components for hex colors returns nothing.
- `getCatalog()` returns parsed, typed data, and a deliberately malformed API response throws a Zod error
  naming the offending field.
- Both light-on-dark contrast ratios pass WCAG AA.

## Done when

The site looks like a deliberate brand rather than a starter template, and no page component knows the API
exists.

## Notes from the build

- Next.js 16's `next dev` auto-generates `AGENTS.md`/`CLAUDE.md` stub files in `web/` on every run
  (pointing agents at `node_modules/next/dist/docs/` for breaking-change context). They'd shadow this
  repo's own root `CLAUDE.md` conventions and get regenerated even if deleted, so they're disabled via
  `agentRules: false` in `next.config.ts` rather than fought on every dev run.
- The signature visual motif is a "spec plate" treatment for anything reading out a hard number
  (`SpecList`, `PriceTag`): uppercase IBM Plex Mono labels with wide tracking, tabular numerals, hairline
  dividers — it reads like a stenciled equipment placard rather than a generic stat block, and ties the
  Oswald/Inter type pairing together.
- The default gray used for the most-muted text token (`--color-ink-faint`) initially measured 3.64:1
  against the canvas color — under the 4.5:1 AA floor for normal-size text even though it looked fine by
  eye. Contrast ratios need computing, not eyeballing; see the WCAG numbers actually used in the palette.
- `Footer`'s copyright year used `new Date().getFullYear()` directly, which Cache Components rejects
  during prerendering as an unstable value. Fixed by moving it into its own `'use cache'` helper with
  `cacheLife('days')` rather than opting the whole footer out of static rendering.
