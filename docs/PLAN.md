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

| # | Stage | Status |
|---|---|---|
| 0 | [Foundations](stages/00-foundations.md) — repo, scaffolds, Compose, CI | **Complete** |
| 1 | [Backend catalog](stages/01-backend-catalog.md) — models, seed, catalog API, pricing & rules | **Complete** |
| 2 | [Design system & shell](stages/02-design-system.md) — tokens, header/footer, API client | **Complete** |
| 3 | [Marketing pages](stages/03-marketing-pages.md) — home, platforms, purposes, SEO | Not started |
| 4 | [Configurator](stages/04-configurator.md) — viewer, build state, live pricing, rules | Not started |
| 5 | [Quote pipeline](stages/05-quote-pipeline.md) — server-authoritative submission, email | Not started |
| 6 | [Admin & revalidation](stages/06-admin-revalidation.md) — quote listing, cache webhook | Not started |
| 7 | [Polish & deploy](stages/07-polish-deploy.md) — perf, a11y, Fly + Vercel + Neon | Not started |

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
│       ├── main.py
│       ├── config.py           # pydantic-settings
│       ├── db.py
│       ├── models/             # SQLModel tables
│       ├── schemas/            # Pydantic request/response models
│       ├── routers/            # catalog.py, builds.py, quotes.py, admin.py
│       ├── services/           # pricing.py, rules.py, mailer.py, revalidate.py
│       └── seed.py
└── web/                        # Next.js 16 app
    ├── next.config.ts          # cacheComponents: true
    └── src/
        ├── app/
        ├── components/
        ├── lib/                # api client, build encoding, pricing mirror
        └── styles/
```
