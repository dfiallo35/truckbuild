# Stage 7 — Polish and deploy

**Goal:** the site is fast, accessible, and live.

**Prerequisite:** Stage 6 checkpoint passes.

## Steps

1. **Performance** — `next/image` with AVIF/WebP for all photography, `next/font` for self-hosted fonts,
   preloaded configurator layer images for the current step, and a bundle-size check on the configurator
   route.
2. **Accessibility and responsive passes** across all breakpoints. Verify the configurator on a phone, where
   the two-pane layout must collapse to stacked viewer-over-panel.
3. **Analytics and error tracking** on both services.
4. **Deploy the API** — `api/Dockerfile` → `fly launch`, `DATABASE_URL` pointed at Neon, migrations run on
   release. Configure CORS to the production web origin only.
5. **Deploy the web app** — Vercel, with `API_BASE_URL` and `REVALIDATE_SECRET` set.
6. **Seed production**, then smoke-test the full path.

## Checkpoint — production smoke test

1. Load `/` — three platform cards render with starting prices from the API.
2. **Start Customizing** on Bristlecone → `/configurator/bristlecone`.
3. Select options; the price bar updates and the URL gains `?o=...`.
4. Copy the URL into a new tab; the identical build restores.
5. Hit the winch/bumper incompatibility; an inline explanation appears.
6. Submit a quote; `/thank-you` shows a reference number.
7. The quote appears via the admin endpoint with a matching total.

Lighthouse targets on `/` and `/builds/bristlecone`: Performance 90+, Accessibility 95+, SEO 100.

## Done when

The production smoke test passes end to end and the Playwright configurator spec runs green against the
deployed site.
