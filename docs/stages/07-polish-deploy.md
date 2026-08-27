# Stage 7 — Polish and deploy

> **Status: steps 1–3 complete and verified 2026-08-27. Steps 4–6 are blocked on accounts.**
> Everything that can be built and proven locally is done; the deploy itself needs Neon, Render,
> and Vercel accounts that only the owner can create. `docs/deploy.md` is the runbook, and the
> checkpoint below runs against a deployment the moment one exists.

**Goal:** the site is fast, accessible, and live.

**Prerequisite:** Stage 6 checkpoint passes.

## Steps

1. **Performance** — `next/image` with AVIF/WebP for all photography, `next/font` for self-hosted fonts,
   preloaded configurator layer images for the current step, and a bundle-size check on the configurator
   route.
2. **Accessibility and responsive passes** across all breakpoints. Verify the configurator on a phone, where
   the two-pane layout must collapse to stacked viewer-over-panel.
3. **Analytics and error tracking** on both services.
4. **Deploy the API** — `api/Dockerfile` → Render (`api/render.yaml`), `DATABASE_URL` pointed at Neon,
   migrations run on deploy. Configure CORS to the production web origin only.

   > Changed from Fly.io mid-stage. Fly ended its free allowance for new organizations in late 2024,
   > and this deployment is a test of the page rather than a commercial launch, so the stack moved to
   > free tiers throughout: Neon + Render + Vercel Hobby. The trade-offs that buys — a sleeping API
   > and Hobby's commercial-use restriction — are written up in `docs/deploy.md`.
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

## What is done

Steps 1–3, verified against real command output rather than inspection:

| Step | Evidence |
|---|---|
| 1. Performance | `next/image` + AVIF/WebP and `next/font` were already in place from Stage 2–4. Added `pnpm bundle:check` (`web/scripts/bundle-budget.mjs`), which reads per-route gzipped JS back out of the prerendered HTML and fails CI over budget. Configurator: **192.3 KiB gz** against a 210 KiB budget. Viewer layers now carry an explicit `fetchPriority`, so the open step's images win the bandwidth race |
| 2. Accessibility & responsive | 22 axe scans (11 pages × 2 breakpoints) at WCAG 2.1 AA, plus keyboard-operation and stacked-layout specs. **45 passed, 5 skipped** (mobile keyboard specs, deliberately) |
| 3. Analytics & error tracking | Vercel Analytics + Speed Insights on the web; Sentry-when-configured over always-on structured JSON request logs on the API; `X-Request-ID` correlating the two. 10 new pytest cases, heaviest on the scrubber |

Checkpoint items 1–7 all pass against the local production build. Item 7 verified directly: a quote
submitted by the spec stored at **$216,700** — base $214,500 plus the $2,200 bumper — and the admin
endpoint returned 401 without its token.

**Not done:** Lighthouse against a deployment, and the "runs green against the deployed site" half of
*Done when*. Both need a URL.

## Two real accessibility defects this stage found

Worth recording because neither was visible by reading the code, and both had been shipped since
Stage 2:

- **Contrast.** The step rail's summary line used `ink-faint`, which lands at roughly 4.3:1 on
  `canvas-overlay` — under the 4.5:1 AA floor for text that size. It only failed on the *active*
  step, which is why nobody caught it. Now `ink-muted`.
- **Links distinguished by colour alone.** The privacy page's mail link underlined on hover only,
  failing WCAG 1.4.1 — and hover is not a state a keyboard or touch user ever passes through.

## Notes from the build

- **`next dev` and `next build` cannot share a directory.** A dev server left running from earlier in
  the day kept rewriting `.next` underneath every production build, leaving prerendered HTML from one
  build referencing chunk hashes from another. Every static asset then 404s, `nosniff` refuses the
  404 body, the configurator never hydrates, and the page sits on its Suspense fallback forever — a
  failure that looks like a hydration bug and is not. Stop the dev server before building.
- **Playwright therefore runs on port 3100, and never reuses an existing server.** `reuseExistingServer`
  on 3000 silently attaches to whatever `next dev` is serving, so the suite passes or fails for reasons
  unrelated to the build under test. This cost an hour; the config comment exists so it costs nobody
  else one.
- **`playwright install --no-shell` is a trap for headless runs.** It skips `chrome-headless-shell`,
  which is exactly what default headless mode launches, so every spec fails with "Executable doesn't
  exist". The config now sets `channel: "chromium"` to use the full browser — one download instead of
  two, and closer to a real visitor's browser besides.
- **Options reference each other by name, so option locators must be anchored.** The winch's conflict
  hint contains the string "Heavy-Duty Winch Bumper", so an unanchored `getByRole` match resolves to
  two controls. `e2e/support.ts` anchors on `^`.
- **`.check()` does not work on a visually hidden input.** The option inputs are `sr-only` with a
  `<label>` wrapping them; Playwright clicks the input, the label intercepts it, and the call times
  out. `choose()` clicks the label — which is what a person does anyway — rather than reaching for
  `force: true` and suppressing the actionability checks worth keeping.
- **Adding a Python dependency needs `--renew-anon-volumes`.** Compose keeps an anonymous volume on
  `/srv/.venv`, and Docker reuses it across rebuilds, so `--build` alone leaves the container on the
  old virtualenv. It surfaces as `ModuleNotFoundError` for a package that is plainly installed, and
  the API hangs rather than erroring — which reads like a database problem.
