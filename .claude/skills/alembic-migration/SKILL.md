---
name: alembic-migration
description: Generating, reviewing, and applying Alembic migrations in TruckBuild's api/ service. Use this whenever a SQLModel table changes shape — api/app/modules/catalog/infrastructure/postgres/tables.py or api/app/modules/quotes/infrastructure/postgres/tables.py — new table, new column, changed type, new constraint, new enum, new index — and whenever someone asks to add a field, add an entity, or run migrations. Autogenerate produces plausible-looking migrations that are wrong about enums, constraints, and server defaults often enough that reading the output before committing is part of the job rather than an optional extra, so do not treat a generated migration as finished work.
---

# Alembic migrations

## Why generated migrations get reviewed here

This project learned it directly, back when the catalog schema was first built: autogenerate gets
enums and constraints wrong often enough that reviewing the output is not optional. This is not
distrust of the tool — autogenerate
compares model metadata against the database and is genuinely good at columns and tables. It is
unreliable at exactly the things this schema depends on:

- **Enums.** Selection mode (`single` | `multi`), display style (`card` | `swatch` | `toggle`), and
  rule kind (`requires` | `excludes`) are enumerated. Postgres enum types have to be created and
  dropped explicitly, and autogenerate frequently emits a column referencing a type it never created,
  or an `alter` that silently drops values.
- **Constraints.** Slug uniqueness is the backbone of the whole data model — slugs are the public
  identifiers in URLs and shared builds. A unique constraint autogenerate declined to notice is a
  duplicate-slug bug waiting for production data.
- **Server defaults and nullability.** Adding a non-null column to a table with existing rows needs a
  server default or a backfill. Autogenerate emits the `add_column` and leaves the failure for
  whoever runs it against a non-empty database.
- **Deletes it did not mean.** A model file that failed to import cleanly looks identical to a model
  that was deleted. The resulting migration drops the table.

## Workflow

Before editing the model, get its blast radius from the CodeGraph index at `.codegraph/`:

```bash
codegraph explore "Option"     # the SQLModel table, its Pydantic schema, the router, the seed upsert
```

A shape change is only ever finished at the far end of that list, and reading it first is what keeps
the migration from being the only thing that got updated. Then generate:

```bash
docker compose exec api alembic revision --autogenerate -m "add option layer image"
```

Then, before anything else, **read the generated file end to end.** Specifically check:

1. Does `upgrade()` do only what you intended, and nothing more? Unexplained drops mean an import
   problem, not a schema change.
2. Are enum types created in `upgrade()` and dropped in `downgrade()`?
3. Do new non-null columns have a `server_default`, or a backfill step before the constraint lands?
4. Are unique constraints on slug columns present?
5. Is `downgrade()` actually the inverse, or the stub Alembic emitted?

Then apply and verify it survives a round trip:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
```

A migration that cannot downgrade is a migration that cannot be rolled back in production. Fix it now
while the only cost is your own time.

Finally, re-seed and confirm idempotency still holds:

```bash
docker compose exec api python -m app.seed
docker compose exec api python -m app.seed    # row counts must not change
```

## Things specific to this project

**Run migrations through Compose, not the host.** The API container has the environment and the
`db:5432` hostname. On the host, `DATABASE_URL` points at port **5433**, so a host-side Alembic run may
target a different database than you think.

**Seed data does not belong in migrations.** Content lives in `api/seed/catalog.yaml` and is loaded by
`app/seed.py` (a thin CLI over `catalog/application/use_cases.py::SeedCatalogUseCase`), which
upserts by slug. Migrations change shape; the seed loader changes content. Mixing them makes
content unreviewable in diffs and makes migrations unrepeatable.

**Migrations run on deploy in production** (Render, in the start command -- see `docs/deploy.md`). A
migration that needs a manual step is a migration that will fail a deploy at an inconvenient moment.

**One migration per logical change.** Squashing several unrelated schema changes into one revision
makes the rollback story worse for all of them.

## Related

`catalog-change` — the full chain a shape change has to travel; the migration is one step of it.
