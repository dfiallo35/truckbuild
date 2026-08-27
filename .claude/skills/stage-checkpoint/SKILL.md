---
name: stage-checkpoint
description: Runs a TruckBuild stage's checkpoint from docs/stages/ and reports pass or fail against real command output, then updates the stage status only once it genuinely passes. All eight stages are now complete, so its main use today is the CI-equivalent sweep — the lint, format-check, test, and build commands GitHub Actions runs — which must pass before any PR, plus verifying a change against the live deployment. Also use it when asked to verify, check, close out, or sign off a stage, or whether a stage is done.
---

# Verifying a stage

## How this project is organized

The build was eight staged, independently reviewable steps. `docs/PLAN.md` is the index and carries the
status table; each `docs/stages/NN-*.md` file has steps, a runnable **Checkpoint**, and **Done when**
criteria. A stage did not begin until the previous checkpoint passed — that gate is the whole point of
the structure, and skipping it moves the failure later where it costs more.

> **All eight stages (0–7) are complete and the site is live.** There is no "next stage" to start, so
> if you came here looking for one, the answer is that ordinary feature work is now the mode. What
> survives the stages is the **CI-equivalent sweep** below — still mandatory before every PR — and
> the deployment verification after it. The stage files stay as a historical record of how the build
> went; do not rewrite them to match the present, that is the whole of their value.

## Workflow

1. **Identify the stage.** If not told which, read the status table in `docs/PLAN.md` and take the
   first one not marked complete. If every row is complete — which is the case today — there is no
   stage to check: skip to the CI-equivalent sweep and the deployment verification below.
2. **Read that stage's file.** The checkpoint commands live there and differ per stage — don't work
   from memory or from this file's examples.
3. **Bring the stack up** if the checkpoint needs it:
   ```bash
   docker compose up -d
   curl -s localhost:8000/healthz
   ```
4. **Run the stage's own checkpoint commands, unmodified**, and capture the actual output.
5. **Run the CI-equivalent sweep** (below). A stage is not done while CI would fail.
6. **Check the "Done when" criteria.** These are often qualitative — "no page component knows the API
   exists", "`pricing.py` imports nothing from `fastapi`" — and are genuinely checkable. Criteria about
   text in a file are grep's job; criteria about who calls what are CodeGraph's, since an indirect call
   through a helper reads as clean under grep:
   ```bash
   grep -rn "fastapi\|sqlmodel" api/app/services/pricing.py api/app/services/rules.py
   grep -rniE "#[0-9a-f]{3,8}" web/src/components/    # tokens only, no hardcoded colors
   codegraph explore "what calls the catalog fetch functions in web/src/lib/api.ts"
   ```
7. **Report against evidence**, then update status.

## The CI-equivalent sweep

These mirror `.github/workflows/ci.yml`. Note the `--check` variants — CI does not accept a formatter
that would have made changes, so running the writing variant locally hides the failure.

**`.github/workflows/ci.yml` is the authority; re-read it rather than trusting this list.** It has
grown before, and a sweep that is a subset of CI is worse than no sweep — it buys confidence that
CI then takes away.

The API job:

```bash
cd api
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run python -m app.seed --no-revalidate    # run twice: CI checks the upsert is idempotent
uv run pytest -q
```

The web job — note it runs **against a live API**, which is why `docker compose up -d` (or a local
uvicorn) has to be up first, and why a build failure "collecting page data" is usually a missing API
rather than a broken page:

```bash
cd web
pnpm install --frozen-lockfile
pnpm lint
pnpm exec prettier --check .
pnpm test                     # vitest — the TS half of the pricing mirror
pnpm build                    # output must contain `- Cache Components enabled`
pnpm bundle:check             # after the build, not before
pnpm exec playwright test     # configurator, a11y, responsive
```

`pnpm test`, `pnpm bundle:check`, and the Playwright run are the three most commonly skipped, and all
three are in CI. Skipping them locally is how a PR arrives red.

Never pipe these through `tail` or `head`. Doing so replaces the command's exit status with the
pager's, so a failing suite reports success — this has already bitten once in this repo. If output is
long, redirect to a file and read it, keeping the exit code intact:

```bash
pnpm build > /tmp/build.log 2>&1; echo "EXIT=$?"
```

On a slow connection, `pnpm install` needs `--fetch-timeout 600000` or it times out mid-fetch.

## Verifying against the deployment

The site is live, so "it works locally" is no longer the end of the check. The same specs run against
the deployment — that is what `E2E_BASE_URL` is for, and it is how the Stage 7 checkpoint was executed
rather than clicked through:

```bash
cd web
E2E_BASE_URL=https://truckbuild.vercel.app pnpm e2e
```

Expect **43 passed, 7 skipped**. The 7 skips are deliberate: the mobile keyboard specs, and
`quote.spec.ts`, which stores a real lead and refuses a non-local target without `E2E_ALLOW_WRITES=1`.
Set that only when a real submission is genuinely intended, and say so in the report.

A quick manual pass on the two services:

```bash
curl -s https://truckbuild-api.vercel.app/healthz                                   # {"status":"ok",...}
curl -o /dev/null -w '%{http_code}\n' https://truckbuild-api.vercel.app/v1/admin/quotes   # expect 401
curl -s https://truckbuild.vercel.app/ | grep -oE '\$[0-9,]+' | sort -u            # prices from the API
```

Two things that make a deployment check misread if you do not know them:

- **The first request pays a cold start.** A single spec timing out on `page.goto` while every other
  passes is a boot, not a regression. `playwright.config.ts` already raises the timeout for a remote
  `E2E_BASE_URL`; if you see it anyway, re-run the one spec before reporting a failure.
- **A migration is not part of a deploy.** If the deployed API is erroring on queries after a merge,
  check `alembic current` against production before debugging anything else — see `alembic-migration`.

## Stage-specific checks worth remembering

- **Stage 0 onward:** `pnpm build` output must include `- Cache Components enabled`. If that line is
  missing, `next.config.ts` is not being picked up and every caching assumption downstream is void.
- **Stage 1:** re-run the seed twice; row counts must be unchanged. Every `requires`/`excludes` rule
  needs a test for both the satisfied and the violated case.
- **Stage 3:** platform and purpose routes must appear as prerendered in the build output, not
  dynamic. A route that went dynamic has a catalog read that escaped the cache.
- **Stage 4:** the URL round trip — configure a build, copy the URL with `?o=...` into a new tab, and
  confirm the identical build restores.
- **Stage 5:** re-POST a quote with a tampered `total_cents` and confirm the server stores its own
  computed price.
- **Stage 6:** the admin endpoints must return 401 without the bearer token.

## Reporting and updating status

Report what you actually ran and what it actually printed. If something failed, say so with the output
rather than describing it as nearly passing — the value of a checkpoint is entirely in its being an
honest gate, and a stage waved through is a stage whose problems surface during the next one.

Only after everything passes, update both places that record status:

- the row in the `docs/PLAN.md` stage table
- the header of the stage file, matching the existing convention:
  `> **Status: complete.** Checkpoint verified YYYY-MM-DD.`

If the stage surfaced something worth remembering — a tool that behaved unexpectedly, a workaround
that was not obvious — add it under a "Notes from the build" heading in the stage file. Stage 0 does
this, and those notes are the reason the port-5433 and BuildKit decisions are still understandable.

## Then open the PR

A passing checkpoint is the signal that the stage is ready for review, so finish by opening a pull
request rather than leaving the work committed locally. Use the `open-pr` skill — the `gh` CLI is not
installed here, so this goes through the GitHub MCP tools.

The checkpoint output you just captured is the PR body's verification section. Carry it over as a
table rather than summarizing it; the reviewer wants what the commands actually printed.
