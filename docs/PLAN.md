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
