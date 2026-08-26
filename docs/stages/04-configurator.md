# Stage 4 — The configurator

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
