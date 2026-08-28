# Stage 13 — Seeding, the web app, and the narrative

> **Status: complete.** Checkpoint verified 2026-08-28.

**Goal:** the seed path goes through the same layers as everything else, the three real seam
problems in `web/src/lib/` are fixed, and the documentation describes the code that exists.

**Prerequisite:** Stage 12 checkpoint passes.

## Steps

1. **Seeding becomes a use case, in the catalog module.** `seed(session, catalog)` in `app/seed.py`
   is already the one function in the codebase shaped like one — it takes its session, returns a
   value, and knows nothing about HTTP. It is also unambiguously catalog work. Split it three ways:

   - the YAML read to `catalog/infrastructure/catalog_file.py`,
   - the upsert-by-slug logic to `catalog/application/use_cases.py::SeedCatalogUseCase`, over
     `IPlatformRepository` and `ICacheInvalidator`,
   - `app/seed.py` stays as a thin `argparse` adapter at the top level — a second entrypoint into
     the same modules `main.py` assembles, which is the point of keeping wiring out of them.

   **The module path and the `--no-revalidate` flag must not change.** CI invokes
   `python -m app.seed --no-revalidate` twice in a row to prove the upsert is idempotent, and
   `README.md`, `docs/setup.md` and `docs/deploy.md` all print the command.

   This is also where `UpdateUseCase` stops being unused: an upsert is a create-or-update, and the
   seed is the one writer the catalog has.

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
   tree and a **"The rules"** section in place of "Boundaries that must hold", covering the layer
   rule inside each module, the `admin → quotes → catalog → core` direction between them, the facade
   rule that keeps one module out of another's internals, and the two new ones this migration bought:
   **a domain that imports no ORM** and **a presentation that writes no query**. The document should
   say which tool checks which, so the next reader knows what would actually fail.

   Say plainly that this is a **modular monolith**: one process, one database, one deployable, with
   module boundaries drawn where a service boundary would go if it ever needed to. Someone reading
   `app/modules/` will otherwise wonder which of them is deployed separately, and the answer — none,
   deliberately — is worth one sentence.

   Add a short **"Adding a module"** section: the twelve files, in dependency order, and the four
   wiring points (`main.py`, the module's `dependencies.py`, `SQLModel.metadata` via the table
   import, and an Alembic revision). The layout only pays off if the next person extending the
   service knows where a new feature goes and which contracts it inherits for free.

4. **Record the trades in [decisions.md](../decisions.md).** Three rows, all of which a reader will
   otherwise have to reverse-engineer:

   - **Entities are separate from tables.** Pure pydantic in `domain/models.py`, SQLModel in
     `infrastructure/postgres/tables.py`, a mapper between. It costs roughly 150 lines of mapper
     code and one more place to add a field; it buys a `domain/` that imports no ORM, which is what
     `Domain forbids persistence` checks and what lets the pricing mirror rest on real entities
     rather than on shim types.
   - **The layout is adapted from `dfiallo35/property-management`**, with the deviations listed in
     [Stage 9](09-core-kernel.md#deviations-from-the-reference-and-why) — FastAPI `Depends` over
     `dependency_injector`, sync over async, `limit`/`offset` over `page`/`size`, SQLModel tables,
     no i18n.
   - **`UpdateUseCase`, `DeleteUseCase` and `BatchUpdateUseCase` have few or no callers.** They are
     the generic CRUD half of the kernel, carried because the set is easier to reason about whole
     than à la carte, and marked `# pragma: no cover` where unreached rather than quietly dragging
     the coverage number down.

5. **Rewrite `CLAUDE.md`'s architecture section and the `.claude/skills/` that name moved paths.**
   `catalog-change`, `alembic-migration` and `pricing-mirror` all name files that this migration
   moved; a skill pointing at a path that no longer exists is worse than no skill. Add a
   **`new-module`** skill covering step 3's checklist — the same role
   `new-feature-module` plays in the reference repo.

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

Finally, the check that the docs are true rather than aspirational: every path named in
`docs/architecture.md`, `CLAUDE.md`, and each `.claude/skills/*/SKILL.md` must exist.

```bash
cd .. && grep -rhoE 'api/app/[a-z_/]+\.py|web/src/[a-zA-Z/.]+\.tsx?' \
  docs/ CLAUDE.md .claude/skills/ | sort -u | while read -r p; do
    [ -e "$p" ] || echo "MISSING: $p"
  done
```

## Done when

Re-seeding twice leaves the row counts unchanged, the CI-equivalent sweep is green for both
services, both halves of the pricing mirror still pass against `fixtures/pricing-cases.json`
unchanged, the path check above prints nothing, and `docs/architecture.md` describes the code that
exists.

## Notes from the build

- **`upsert_from_catalog`'s rule sync is global, not per-platform.** `_sync_rules` resyncs the
  whole `optionrule` table against whatever `catalog["rules"]` names — true of the original
  `app/seed.py` too, just never reachable before, since its one real caller always passed the
  complete seed catalog. Writing `test_seed_upsert.py` against a synthetic single-platform catalog
  hit this directly: passing an empty `rules` list wiped every real platform's rules out from
  under the rest of the test session. Fixed by having the test read and pass back the real rules
  unchanged, and documented as a caveat on `upsert_from_catalog` itself — a caller other than the
  full seed must carry the complete rule set or it will silently drop rules it didn't touch.
- **`upsert_from_catalog` has to commit, not just flush.** Unlike `create`/`update`, which only
  flush and leave the caller to commit, this is the one write that must be durable before
  `SeedCatalogUseCase` invalidates the cache right after — otherwise the revalidated page can
  refetch a value it can't yet see under read-committed isolation. Same shape of reasoning as
  `QuoteRepositoryPostgres.create`'s early commit, for a different reason.
- **`docs/setup.md` had a stale `api/app/config.py` reference** predating stage 9's move to
  `app/core/config.py`, caught only by actually running the path-existence checkpoint rather than
  by review.
