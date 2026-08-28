# Stage 11 — Seeding, the web app, and the narrative

> **Status: not started.**

**Goal:** the seed path goes through the same layers as everything else, the three real seam
problems in `web/src/lib/` are fixed, and the documentation describes the code that exists.

**Prerequisite:** Stage 10 checkpoint passes.

## Steps

1. **Seeding becomes a use case, in the catalog module.** `seed(session, catalog)` in
   `app/seed.py` is already the one function in the codebase shaped like one — it takes its session,
   returns a value, and knows nothing about HTTP. It is also unambiguously catalog work. Split it
   three ways: the YAML read to `catalog/infrastructure/catalog_file.py`, the upsert-by-slug logic
   to `catalog/application/use_cases/seed_catalog.py` over `PlatformRepository`, and `app/seed.py`
   stays as a thin `argparse` adapter at the top level — a second entrypoint into the same modules
   `main.py` assembles, which is the point of keeping the wiring out of them.

   **The module path and the `--no-revalidate` flag must not change.** CI invokes
   `python -m app.seed --no-revalidate` twice in a row to prove the upsert is idempotent, and
   `README.md`, `docs/setup.md`, and `docs/deploy.md` all print the command.

2. **`web/` gets a light pass, not a restructure.** `web/src/lib/` is already acyclic and layered:
   every catalog read goes through `lib/catalog.ts`, and nothing outside it imports `lib/api.ts`.
   Imposing four directories on a Next.js app would fight the framework's own conventions — where
   `'use cache'` and `'use server'` may appear, what `app/` means — for no gain. Three targeted
   fixes, and nothing else:

   - **Split `lib/api.ts`.** Two hundred and nineteen lines holding two different things: the
     contract (Zod schemas and the types inferred from them) and the transport (`ApiError`,
     `apiBaseUrl`, `fetchJson`, `postLead`). They become `lib/contract.ts` and `lib/api.ts`. Every
     consumer already imports its types from one place, so this is import-path churn and no logic.
   - **Move `formatCents` and `formatDelta` out of `lib/pricing.ts`.** They are `Intl` presentation
     sitting inside the module that mirrors `pricing.py`, which makes the mirror's boundary read as
     fuzzier than it is — the Python side has no counterpart to them and never will. They move to
     `lib/format.ts` and `pricing.ts` becomes arithmetic on both sides.
   - **Extract the build view model.** `priceBuild` and `validateSelection` are each called from two
     places, `ConfiguratorShell.tsx` and `BuildRequest.tsx`, with duplicated `useMemo` derivation —
     and `BuildRequest` independently re-derives the whole build from the URL rather than being told
     it. One `lib/buildView.ts` deriving `{ selected, breakdown, violations }` from a platform and
     its search params, consumed by both.

   Explicitly not in scope: `@/domain/*` path aliases, moving anything out of `app/` or
   `components/`, and any change to where `'use cache'` or `'use server'` sits.
   `web/tsconfig.json` and `web/vitest.config.mts` keep their single `@ → ./src` alias, which is two
   files that would otherwise have to stay in sync forever. The module split is a backend decision;
   `web/` is one deployable rendering one product, and importing the idea there would be cargo cult.

3. **Rewrite the narrative.** [architecture.md](../architecture.md) needs a new "Where things live"
   tree and a **"The three rules"** section in place of "Boundaries that must hold" — the layer rule
   inside each module, the `admin → quotes → catalog → core` direction between them, and the facade
   rule that keeps one module out of another's internals. The boundaries are largely the same ones;
   what changed is that they are now checked, and the document should say which tool checks which,
   so the next reader knows what would actually fail.

   Say plainly that this is a **modular monolith**: one process, one database, one deployable, with
   module boundaries drawn where a service boundary would go if it ever needed to. Someone reading
   `app/modules/` will otherwise wonder which of them is deployed separately, and the answer — none,
   deliberately — is worth one sentence.

   Add a short **"Adding a module"** section too. The layout only pays off if the next person
   extending the service knows where a new feature goes and which contracts it inherits for free.

   Add a row to [decisions.md](../decisions.md) recording the trade taken here: **SQLModel tables
   are the entities.** There are no separate domain dataclasses and no mappers, which saves roughly
   a hundred and fifty lines and keeps one model of the truth — at the cost of every module's
   `domain/` importing `sqlmodel`, so the dependency rule is relaxed at the centre rather than
   absolute. The
   import-linter contracts are written around that exception instead of pretending it is not there,
   and `pricing.py` and `rules.py` keep the stricter no-`sqlmodel` rule individually, because that
   purity is what the TypeScript mirror rests on.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check . && uv run lint-imports
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run python -m app.seed --no-revalidate      # twice: row counts must not move
uv run pytest -q

cd ../web
pnpm lint && pnpm format:check && pnpm test && pnpm build && pnpm bundle:check && pnpm e2e
```

`pnpm build` must still print `- Cache Components enabled`. That line is the check, not the config
file — see [cache-and-revalidation](../../.claude/skills/cache-and-revalidation/SKILL.md).

## Done when

Re-seeding twice leaves the row counts unchanged, the CI-equivalent sweep is green for both
services, both halves of the pricing mirror still pass against `fixtures/pricing-cases.json`
unchanged, and `docs/architecture.md` describes the code that exists.
