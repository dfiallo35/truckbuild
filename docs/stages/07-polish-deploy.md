# Stage 7 — Polish and deploy

> **Status: complete.** Checkpoint verified 2026-08-27 against the live deployment.
> Site: <https://truckbuild.vercel.app> · API: <https://truckbuild-api.vercel.app> · Postgres: Neon.
> `docs/deploy.md` is the runbook.

**Goal:** the site is fast, accessible, and live.

**Prerequisite:** Stage 6 checkpoint passes.

## Steps

1. **Performance** — `next/image` with AVIF/WebP for all photography, `next/font` for self-hosted fonts,
   preloaded configurator layer images for the current step, and a bundle-size check on the configurator
   route.
2. **Accessibility and responsive passes** across all breakpoints. Verify the configurator on a phone, where
   the two-pane layout must collapse to stacked viewer-over-panel.
3. **Analytics and error tracking** on both services.
4. **Deploy the API** — a Python function on Vercel (`api/vercel.json`), `DATABASE_URL` pointed at
   Neon's pooled endpoint, CORS restricted to the production web origin.

   > The host changed twice. Fly.io first, dropped when Fly ended its free allowance for new
   > organizations; then Render, which could not clone this **private** repository — that needs both
   > Render's GitHub App on the repo *and* the Render account linked to that GitHub identity, and the
   > second link cannot be made from any API. Rather than block the deploy on a browser
   > authorization, the API moved to Vercel alongside the web app. `api/render.yaml` and the
   > `Dockerfile` are kept as the container description to return to on a paid plan; nothing reads
   > them today. The costs of serverless — no automatic migration step, and a per-instance rather
   > than global rate limiter — are in `docs/deploy.md`.
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

Steps 4–6, verified against the live deployment on 2026-08-27:

| Item | Evidence |
|---|---|
| Neon | Project `truckbuild`, `aws-us-west-2`. Migrated to head and seeded from a workstation against the **direct** URL: 3 platforms, 23 option groups, 54 options, 3 rules, 51 assets |
| API | `truckbuild-api.vercel.app` — `/healthz` 200 `{"environment":"production"}`, `/v1/platforms/bristlecone` 200 returning Bristlecone at 21450000 cents / 9 groups, `/v1/admin/quotes` **401** without a token |
| Web | `truckbuild.vercel.app` — home 200 rendering all three starting prices ($168,900 / $214,500 / $232,000) straight from the API |
| Checkpoint 1–5 | Playwright against the deployment: **43 passed, 7 skipped, 0 failed** |
| Checkpoint 6 | `quote.spec.ts` with `E2E_ALLOW_WRITES=1` — thank-you page returned a reference number |
| Checkpoint 7 | Admin endpoint returned ref `TB-JWWHP6`, `total_cents` **21670000** = $216,700 = base $214,500 + the $2,200 bumper |

Lighthouse against the deployment, both required pages, against the stage's targets:

| Page | Performance (≥90) | Accessibility (≥95) | SEO (=100) | Best Practices |
|---|---|---|---|---|
| `/` | **99** | **100** | **100** | 96 |
| `/builds/bristlecone` | **99** | **100** | **100** | 96 |

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
- **A Vercel Python deploy can succeed while building nothing.** Without `api/vercel.json` naming
  the `fastapi` framework, Vercel detects the project as "Other", runs a Node build, and reports
  success after ~50ms — then every route 404s. The tell is in the build log: `Build Completed in
  /vercel/output [51ms]` with no dependency install above it. A deploy that reports success and
  serves nothing is worse than a failed one, because nothing prompts you to read the log.
- **Vercel Authentication is on by default and answers `302`, not `401`.** Every API route
  redirected to an SSO page, including the server-side fetches the web app makes — which does not
  look like an auth setting, it looks like a broken API. It has to be switched off for a public
  API project.
- **Serverless wants Neon's pooled endpoint, migrations want the direct one.** An idle function
  instance is frozen rather than torn down and keeps its connections, so enough of them against the
  direct endpoint exhaust the limit. Alembic, conversely, wants a real session. Both URLs are in
  use, for different callers.
- **The first request to a deployment pays a cold start, and one spec always eats it.** Against the
  live site the first `page.goto` exceeded the 30s default while every later one finished under 8s,
  so exactly one test failed — always whichever ran first. `playwright.config.ts` now raises the
  timeout only for a non-local `E2E_BASE_URL`; local runs keep the tighter default, where a slow
  page really is a regression.
- **Adding a Python dependency needs `--renew-anon-volumes`.** Compose keeps an anonymous volume on
  `/srv/.venv`, and Docker reuses it across rebuilds, so `--build` alone leaves the container on the
  old virtualenv. It surfaces as `ModuleNotFoundError` for a package that is plainly installed, and
  the API hangs rather than erroring — which reads like a database problem.
