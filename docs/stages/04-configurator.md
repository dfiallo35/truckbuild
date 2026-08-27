# Stage 4 — The configurator

> **Status: complete.** Checkpoint verified 2026-08-26.

**Goal:** a buyer can assemble a valid, priced, shareable build.

This is the heart of the product; budget accordingly. It is the one stage worth splitting further if it
starts to sprawl.

**Prerequisite:** Stage 3 checkpoint passes.

## Steps

1. **`/configurator/[slug]` layout** — full-bleed: viewer left/top, step navigation and option panel
   right/bottom, persistent price bar. It escapes the marketing chrome, mirroring the reference site's
   minimal header of logo, "Talk to Sales", and "Exit".
2. **Build state** — a reducer keyed by option group, with the selection encoded into the URL query string
   (`?o=slug-a,slug-b`). URL-as-state gives shareable, refresh-safe, back-button-correct builds for free and
   needs no database round trip.
3. **Viewer** — a layered composite: a base platform image with option layer images stacked by `z-index`,
   cross-fading on change. This delivers most of the perceived value of 3D at a fraction of the cost. Every
   layer is a `next/image` with explicit dimensions; options without a layer simply contribute nothing.
4. **Live pricing** — mirror `price_build` in `web/src/lib/pricing.ts` for instant feedback. This mirror is
   a UX affordance only: **the server price is authoritative**, and both implementations share test fixtures
   so they cannot silently drift.
5. **Rules** — mirror `validate_selection` to flag incompatible options inline, explaining *why* an option
   is unavailable rather than merely greying it out.
6. **Summary panel** — grouped line items, price breakdown, and a "Request this build" CTA.
7. **Accessibility** — full keyboard traversal of steps and options, focus management on step change, and
   `aria-live` announcements for price updates.

## Checkpoint

1. Configure a build; the price bar updates and the URL gains `?o=...`.
2. Paste that URL into a new tab; the identical build restores.
3. Select the 12,000 lb winch without the heavy bumper; an inline explanation appears rather than a silent
   block.
4. Traverse every step and select every option using only the keyboard.

## Done when

A build can be configured, shared by URL, restored from that URL, and cannot reach an invalid combination.

## Notes from the build

- **No migration was needed for the viewer.** `Asset` already carried `thumbnail` and `layer`
  kinds and an `option_id`, so layer images were a content and wire-shape change only. An
  option's layer is `kind=layer, option_id=…` with `sort_order` holding the z-index; the
  platform's base image is the same kind with `platform_id` set and z 0. `OptionOut` gained
  `layer` and `swatch`, `PlatformOut` gained `viewer_base`.
- **The Zod asset enum only listed `hero | gallery`.** Adding swatches (`kind: thumbnail`)
  would have failed the parse at the boundary — caught by `tsc` before it ever ran, which is
  the whole argument for parsing rather than casting in `lib/api.ts`.
- **Marketing chrome moved into a `(site)` route group.** The configurator is full-bleed with
  its own bar, and a nested layout cannot remove a parent's header. The root layout now holds
  only the document shell; `(site)/layout.tsx` holds `Header`/`Footer`. Route groups add no URL
  segment, so every path, `generateStaticParams`, and metadata file resolved unchanged.
- **The URL is written with `history.replaceState`, not a router navigation.** Pushing an entry
  per click would take thirty presses of Back to leave the page. Back and Forward across
  entries that do exist still restore the build they encode — that is what the `popstate`
  listener in `ConfiguratorShell` is for. Reading the initial selection through
  `useSearchParams` (inside the page's `Suspense` boundary) is what keeps the shell
  prerenderable under Cache Components.
- **`decodeSelection` repairs rather than throws.** A shared build URL outlives the catalog it
  was built from: unknown slugs are dropped, a single-select group keeps only its first named
  option, and an unmentioned required group falls back to its default. A selection that breaks
  a rule is deliberately *kept* — the page cannot explain a conflict it silently discarded.
- **Conflicts are explained on both sides of the click.** An unselected option says what it
  needs or conflicts with before it is chosen; a conflict already in the build gets a notice
  with a one-press resolution. Submission is what is blocked, not selection — which is what the
  checkpoint asks for, and Stage 5's server-side re-validation is what actually enforces it.
- **Vitest is now part of CI** (`pnpm test` in the web job). It reads `fixtures/pricing-cases.json`
  and `api/seed/catalog.yaml` from the repo root, so the mirror fails loudly if only one side moves.
- **Placeholder layer art is generated from one shared coordinate system**, so the base and
  every option layer align by construction rather than by eye. Two compromises worth knowing:
  the paint finish repaints the upfit body only (the cab stays factory, which is both true of
  real upfits and keeps cab and finish options off the same pixels), and a body-extension layer
  stays neutral steel rather than tracking the chosen paint. Real photography is a file
  replacement at the same paths.
