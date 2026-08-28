---
name: new-module
description: Scaffolding a new feature module in TruckBuild's api/ service — the twelve files a module needs and the four places it has to be wired in. Use this whenever someone asks to add a new feature module, a new vertical slice, or asks "where does X go" about a piece of backend functionality that doesn't fit inside catalog, quotes, or admin. Do not use it for adding a field, endpoint, or table to an existing module — see catalog-change or alembic-migration for that.
---

# Adding a module

## Before starting

A module earns its own directory under `api/app/modules/` when it owns a distinct piece of the
domain that the existing three don't — not for every new endpoint. `admin` is the minimal case: it
owns no tables and so has no `domain/` and no `infrastructure/`, only `application/` and
`presentation/`. If the new thing is a field or an endpoint on an existing entity, it belongs in
`catalog` or `quotes`, not a new module — see the `catalog-change` skill.

Read [docs/architecture.md](../../../docs/architecture.md)'s "The rules" section first. Every rule
there — layer direction, module direction, facades, domain purity — applies to the module being
added, and `uv run lint-imports` enforces all of them the moment the new files import anything.

## The twelve files, in dependency order

Each layer only needs what came before it, so build in this order and every import will already
resolve:

1. **`domain/models.py`** — pure pydantic entities, extending `core`'s `BaseEntity`. No `fastapi`,
   no `sqlmodel` import, ever — this is what `Domain forbids persistence` checks.
2. **`domain/interfaces.py`** — the module's ports. At minimum an `I<Name>Repository` extending
   `core.domain.interfaces.IBaseRepository`; add narrower read methods here if other modules or
   this module's own use cases need lookups the generic `list`/`count` can't express (see
   `IPlatformRepository.by_slug`/`.slugs` for the pattern).
3. **`domain/filters.py`** — a `BaseFilter` subclass per queryable entity, keying off the
   `_eq`/`_in`/`_ilike`/`_gte`/`_lte` suffix convention `BaseRepositoryPostgres.filter` reads.
4. **`infrastructure/postgres/tables.py`** — the SQLModel tables. Pin `__tablename__` explicitly;
   SQLModel derives it from the class name otherwise, and a later rename would autogenerate as
   `drop_table` + `create_table`.
5. **`infrastructure/postgres/mappers.py`** — table → domain and domain → table. Assemble from
   already-loaded rows; a mapper that holds a session and lazy-loads is how the N+1 the catalog
   module fixed in stage 10 gets reintroduced.
6. **`infrastructure/postgres/repositories.py`** — the port's Postgres implementation, extending
   `core.infrastructure.postgres.repositories.BaseRepositoryPostgres` and the domain interface
   from step 2. Every query the module makes belongs in one fixed-statement-count method here —
   not a query per attribute access above this layer.
7. **`application/dtos.py`** — request/response shapes, on `core`'s `BaseOutput`/
   `BaseCreateRequest`/etc. where the operation is a standard CRUD shape.
8. **`application/mappers.py`** — domain → DTO (and DTO → domain for a create/update path).
9. **`application/use_cases.py`** — one class per operation, overriding `BaseUseCase`'s
   `pre_run`/`validate`/`run`/`post_run` hooks. Never override `exec` unless the operation
   genuinely takes something other than the standard shape (see `GetPlatformUseCase.exec`, which
   takes a slug instead of an id, for when that's justified).
10. **`application/services.py`** — the module's facade, extending `core.application.services.
    BaseService`. This is what another module and this module's own router are allowed to see —
    never its `presentation` or `infrastructure`.
11. **`dependencies.py`** — sits beside the four layers, not inside one. This is the module's own
    composition root: it builds the concrete adapter from step 6 and wires it, plus anything
    step 10 needs, into the service. It's the one file in the module allowed to see both an
    adapter and an inner layer.
12. **`presentation/<name>_api.py`** — the router. If it needs another module's data, it declares
    that as a function whose whole body is `raise NotImplementedError` (see
    `app.modules.quotes.presentation.quotes_api.get_platform_repository` for the pattern) — a
    router may never import another module's adapter directly, which is the facade rule.

## The four wiring points

None of these live inside the twelve files above — they're what makes the module reachable.

- **`app/main.py`** — mount the router (`root_router.include_router(<name>_router)`), and if step
  12 declared a port onto another module, add `<declared port>: <that module's dependencies.py
  provider>` to `PORT_BINDINGS`.
- **The module's own `dependencies.py`** (step 11) — built with the module, listed again here
  because it's easy to forget it's also a wiring point for *this* module's router, not just a
  regular application file.
- **`SQLModel.metadata`, via the table import** — `alembic/env.py` has to import the new
  `tables.py` (directly or via the module's `__init__.py`), or autogenerate silently never sees
  the new tables and emits an empty migration. `tests/test_entity_registry.py` fails if this is
  missed — run it before generating a migration, not after.
- **An Alembic migration** — see the `alembic-migration` skill for the full workflow; the short
  version is generate, then read the output end to end before applying it.

## Verifying

```bash
cd api
uv run lint-imports          # layer, module-direction, facade, domain-purity contracts
uv run pytest tests/test_composition_root.py tests/test_entity_registry.py -v
uv run pytest tests/modules/<new-module>/ -v
```

A module that passes `lint-imports` and has every declared port bound is wired correctly even
before its first real test — those two checks are what catch a half-finished module rather than
a broken one.

## Related

`catalog-change` — adding a field or endpoint to an *existing* module (most requests are this,
not a new module).
`alembic-migration` — the migration workflow referenced in wiring point 4.
`docs/architecture.md` — "The rules" and "Adding a module" sections this skill implements.
