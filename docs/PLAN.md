# TruckBuild — Plan Index

A public website for a company that upfits trucks for different purposes, modeled on
[offhighwayvan.aftershock.agency](https://offhighwayvan.aftershock.agency/): a dark, photography-led
marketing site whose commercial centerpiece is a **per-platform configurator**.

A visitor picks a build platform, configures it through option groups, watches the price update live, and
submits the finished build as a qualified lead.

**Outcome:** a deployed two-service application — a Next.js 16 front end and a FastAPI back end — where a
visitor can go from the home page to a submitted, priced, server-validated build, and sales can read those
builds.

## Reference documents

| Document | What it covers |
|---|---|
| [decisions.md](decisions.md) | Locked-in choices and the one architectural tension |
| [domain-model.md](domain-model.md) | Vocabulary, entities, and the placeholder catalog |
| [testing.md](testing.md) | Test strategy across both services |

## Stages

Each stage is independently reviewable and ends in a checkpoint that must pass before the next begins.

Stages 0–7 built and shipped the application. Stages 8–13 restructure the API service that
resulted into a **modular monolith**: feature modules bounded like services, each carrying its own
four clean-architecture layers over a shared `core`, assembled into one FastAPI app at one
composition root. Same behaviour, same wire contract, with every boundary enforced by CI rather than
by convention.

Stage 8 moved the files. Stages 9–13 do the untangling, and take their layout from
[`dfiallo35/property-management`](https://github.com/dfiallo35/property-management), which runs the
same vertical-slice-over-a-shared-`core` shape across fourteen features: pure pydantic entities in
`domain/` with SQLModel tables and a mapper in `infrastructure/`, a `BaseUseCase` template method
and its CRUD subclasses in `application/`, and a router that names none of it. Where this repo
deviates from that reference — FastAPI `Depends` instead of `dependency_injector`, sync instead of
async, `limit`/`offset` instead of `page`/`size` — the deviation is named and justified in
[Stage 9](stages/09-core-kernel.md#deviations-from-the-reference-and-why).

The single line that measures whether the migration worked: **`app/modules/*/domain/` imports no
ORM**, checked by an import-linter contract rather than by review.

Stages 14–17 are product work rather than restructuring: they replace the configurator's 2D layered
image composite with a **real 3D build view**, and introduce the first thing this application stores
outside Postgres. The split that drives them is that **Postgres holds a reference and Vercel Blob
holds the bytes** — a `BuildModel` row carries a URL, a content hash and a size, and the file itself
reaches Blob through `python -m app.assets sync` run by an operator, never through a request.

Two findings shape the whole sequence and are worth knowing before reading any of it:

- **A Vercel function caps request bodies at 4.5 MB**, and GLB models run 5–50 MB. An upload
  endpoint would pass every local test and fail on the first real model in production, so there
  isn't one.
- **The configurator route's client-JS budget is 210 KiB gzipped** and three.js is 130–160 KiB on
  its own, so the viewer is a lazily imported chunk — and `bundle-budget.mjs` has to learn to
  measure one, or it ships unmeasured.

The stages are ordered so that each is independently green: 14 is additive to the wire, 15 fills in
what 14 created, 16 builds the viewer while the 2D composite still exists, and only 17 removes it.

| # | Stage | Status |
|---|---|---|
| 0 | [Foundations](stages/00-foundations.md) — repo, scaffolds, Compose, CI | **Complete** |
| 1 | [Backend catalog](stages/01-backend-catalog.md) — models, seed, catalog API, pricing & rules | **Complete** |
| 2 | [Design system & shell](stages/02-design-system.md) — tokens, header/footer, API client | **Complete** |
| 3 | [Marketing pages](stages/03-marketing-pages.md) — home, platforms, purposes, SEO | **Complete** |
| 4 | [Configurator](stages/04-configurator.md) — viewer, build state, live pricing, rules | **Complete** |
| 5 | [Quote pipeline](stages/05-quote-pipeline.md) — server-authoritative submission, email | **Complete** |
| 6 | [Admin & revalidation](stages/06-admin-revalidation.md) — quote listing, cache webhook | **Complete** |
| 7 | [Polish & deploy](stages/07-polish-deploy.md) — perf, a11y, Vercel + Neon | **Complete** |
| 8 | [Modules & layers](stages/08-modules-and-layers.md) — the move, and import-linter in CI | **Complete** |
| 9 | [The kernel](stages/09-core-kernel.md) — `core` grows its own four layers | **Complete** |
| 10 | [`catalog` slice](stages/10-catalog-slice.md) — entities split from tables, the N+1 goes | **Complete** |
| 11 | [`quotes` slice](stages/11-quotes-slice.md) — one use case per endpoint, ports for mail and rate limiting | **Complete** |
| 12 | [`admin` slice](stages/12-admin-slice.md) — filters, its own DTOs, the full contract set | **Complete** |
| 13 | [Seeding, web & docs](stages/13-seeding-web-docs.md) — closing the migration | **Complete** |
| 14 | [Build model in the catalog](stages/14-build-model-catalog.md) — `BuildModel`, `OptionModelEffect`, additive | Not started |
| 15 | [Blob storage & ingest](stages/15-blob-storage-ingest.md) — `IBlobStore`, GLB validation, `app.assets` | Not started |
| 16 | [The 3D viewer](stages/16-3d-viewer.md) — three.js, lazy chunk, lazy-chunk budgets | Not started |
| 17 | [Retire the 2D composite](stages/17-retire-2d-composite.md) — the enum migration, the docs | Not started |

## Repository layout

```
truckbuild/
├── docker-compose.yml          # postgres + api, for local dev
├── .env.example
├── docs/
├── api/                        # FastAPI service
│   ├── pyproject.toml          # uv-managed
│   ├── Dockerfile
│   ├── alembic/
│   ├── seed/catalog.yaml       # versioned placeholder catalog
│   └── app/
│       ├── main.py             # composition root: mounts each module's router
│       ├── seed.py             # catalog.yaml → Postgres, over the catalog module
│       ├── core/               # the shared kernel — its own four layers
│       │   ├── config.py       #   read by every layer, belongs to none
│       │   ├── domain/         #   BaseEntity · IBaseRepository · BaseFilter · BaseError
│       │   ├── application/    #   BaseUseCase + CRUD subclasses · BaseService · BaseMapper
│       │   ├── infrastructure/ #   BaseTable · BaseRepositoryPostgres · engine · ratelimit
│       │   └── presentation/   #   create_app · error handlers · telemetry · query filters
│       └── modules/            # one package per feature, four layers each
│           ├── catalog/        # domain/ application/ infrastructure/ presentation/
│           ├── quotes/         # domain/ application/ infrastructure/ presentation/
│           └── admin/          # application/ presentation/ — owns no tables
└── web/                        # Next.js 16 app
    ├── next.config.ts          # cacheComponents: true
    └── src/
        ├── app/
        ├── components/
        ├── lib/                # api client, build encoding, pricing mirror
        └── styles/
```
