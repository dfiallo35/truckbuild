---
name: stage-checkpoint
description: Runs a TruckBuild stage's checkpoint from docs/stages/ and reports pass or fail against real command output, then updates the stage status only once it genuinely passes. Use this when asked to verify, check, close out, or sign off a stage, when asked whether a stage is done or what to work on next, before starting the next stage, and before opening a PR for stage work. Also use it as the CI-equivalent sweep — the lint, format-check, test, and build commands GitHub Actions runs — since a stage cannot be complete while CI would be red.
---

# Verifying a stage

## How this project is organized

The build is twelve staged, independently reviewable steps (0–7 built the app, 8–11 restructure the API). `docs/PLAN.md` is the index and carries the
status table; each `docs/stages/NN-*.md` file has steps, a runnable **Checkpoint**, and **Done when**
criteria. A stage does not begin until the previous checkpoint passes — that gate is the whole point of
the structure, and skipping it moves the failure later where it costs more.

## Workflow

1. **Identify the stage.** If not told which, read the status table in `docs/PLAN.md` and take the
   first one not marked complete.
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
   grep -rniE "#[0-9a-f]{3,8}" web/src/components/    # tokens only, no hardcoded colors
   codegraph explore "what calls the catalog fetch functions in web/src/lib/api.ts"
   ```

   Since stage 8, the criteria about *which module may import which* are no longer grep's job either
   — `uv run lint-imports` checks the layer, module-direction, facade, domain-isolation and
   pricing-mirror-purity contracts declared in `api/pyproject.toml`, and it is part of the sweep
   below. Read its output rather than re-deriving the same rules by hand.
7. **Report against evidence**, then update status.

## The CI-equivalent sweep

These mirror `.github/workflows/ci.yml`. Note the `--check` variants — CI does not accept a formatter
that would have made changes, so running the writing variant locally hides the failure.

```bash
cd api
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pytest -q

cd ../web
pnpm install --frozen-lockfile
pnpm lint
pnpm exec prettier --check .
pnpm build
```

Never pipe these through `tail` or `head`. Doing so replaces the command's exit status with the
pager's, so a failing suite reports success — this has already bitten once in this repo. If output is
long, redirect to a file and read it, keeping the exit code intact.

On a slow connection, `pnpm install` needs `--fetch-timeout 600000` or it times out mid-fetch.

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
