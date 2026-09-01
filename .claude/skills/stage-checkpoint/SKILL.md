---
name: stage-checkpoint
description: Runs TruckBuild's CI-equivalent sweep — the lint, format-check, test, and build commands GitHub Actions runs — and reports pass or fail against real command output. Use this before opening a PR for any work in this repo, or when asked to verify that the tree is CI-green. Also covers the historical stage-verification workflow used while the app was being built in staged steps (0–17, all complete, archived to Notion), for reference if staged development ever resumes here.
---

# Verifying the tree (and, historically, a stage)

## How this project is organized

The app was originally built as eighteen staged, independently reviewable steps (0–7 built the app,
8–13 restructured the API into a modular monolith, 14–17 replaced the 2D configurator viewer with a
3D one). All eighteen are complete, and the plan that drove them — `docs/PLAN.md` and `docs/stages/`,
each stage's steps, runnable **Checkpoint**, and **Done when** criteria — has been archived to Notion:
[TruckBuild — Development Plan](https://app.notion.com/p/3ce774db73568150bcd2cb9e6b099239). Ordinary
feature work in this repo today isn't staged; use the CI-equivalent sweep below before any PR.

If staged development resumes (a new `docs/stages/NN-*.md` is added for a large, sequenced piece of
work), the historical workflow was:

1. **Identify the stage.** Read the status table in the plan and take the first one not marked complete.
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

For staged work (historical, or if it resumes), only after everything passes, update both places that
record status: the row in the plan's stage table and the header of the stage file, matching the
existing convention (`> **Status: complete.** Checkpoint verified YYYY-MM-DD.`). If the stage surfaced
something worth remembering — a tool that behaved unexpectedly, a workaround that was not obvious —
add it under a "Notes from the build" heading in the stage file. Stage 0's page in the archived plan
does this, and those notes are the reason the port-5433 and BuildKit decisions are still understandable.

## Then open the PR

A passing checkpoint is the signal that the stage is ready for review, so finish by opening a pull
request rather than leaving the work committed locally. Use the `open-pr` skill — the `gh` CLI is not
installed here, so this goes through the GitHub MCP tools.

The checkpoint output you just captured is the PR body's verification section. Carry it over as a
table rather than summarizing it; the reviewer wants what the commands actually printed.
