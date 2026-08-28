# Stage 9 — Repositories: the queries leave the routers

> **Status: not started.**

**Goal:** no module's `presentation/` layer imports `sqlmodel` or `sqlalchemy`. Every database query
in the service sits behind a port owned by the module whose data it reads.

Today every query is written at its call site. `catalog`'s router issues three extra queries per
platform and relies on lazy-loading `platform.option_groups → group.options` inside the request
session, so the ORM object graph *is* the read model. `quotes`' router owns transaction control and
the reference-collision retry loop. `admin`'s router composes filter conditions, escapes `ILIKE`
wildcards, and paginates — sixty-four lines of it — inside one HTTP handler.

None of that is HTTP's business, and while it lives there the test suite has nowhere to stand: there
is no database fixture and no `dependency_overrides` in `tests/conftest.py`, because there is no seam
at which to substitute anything.

**Prerequisite:** Stage 8 checkpoint passes.

## Where each port lives

A port belongs to the module that owns the data, not to the module that reads it. `admin` lists
leads and revalidates platform slugs, but it defines neither repository — it consumes
`quotes.application.ports.QuoteRepository` and `catalog.application.ports.PlatformRepository`, which
is what `admin → quotes → catalog` means in practice.

| Port | Module | Methods |
|---|---|---|
| `PlatformRepository` | `catalog` | `all()` · `by_slug(slug)` · `rules_for(options)` · `slugs()` |
| `QuoteRepository` | `quotes` | `add(quote)` · `by_ref(ref)` · `page(filters, limit, offset)` |

## Steps

1. **Declare ports as `Protocol`, not `ABC`.** A Protocol means the SQLModel implementation inherits
   nothing and a test fake is a plain class with the right methods — which is the entire reason for
   defining a port rather than just calling the repository directly.
2. **`catalog/infrastructure/persistence.py`** absorbs the query half of `_serialize_platform` from
   the catalog router and the three private helpers from the quotes router — `_platform_by_slug`,
   `_options_of`, `_rules_of`. **Fix the N+1 while the code is in your hands:** eager-load the group
   and option graph and fetch the rules in one query, rather than three per platform. This is the
   one behavioural change the stage permits, and it is invisible on the wire — which is what the
   golden diff is for.
3. **`quotes/infrastructure/persistence.py`** absorbs `_save` — its `session.commit()`, its
   `rollback` on `IntegrityError`, and its `REF_ATTEMPTS` retry — and the whole of `list_quotes`'s
   query composition, `_escape_like` included. The pagination *policy* goes with it:
   `created_at DESC, id DESC` ordering and the one-count-per-page line subquery are decisions about
   how leads are stored and read.

   `MAX_PAGE_SIZE` **stays in the admin router**, because a bound on a query parameter is an HTTP
   concern and belongs where FastAPI can reject it with a 422 before anything else runs.
4. **Wire it per module.** Each module gets a `presentation/dependencies.py` turning
   `Depends(get_session)` into a repository, and the router's signature names the port type. A
   router that can still name `Session` will eventually use it. `core/db.py` keeps providing the
   session; it is the one thing every module's wiring shares.
5. **Tighten the contract.** Add: every module's `presentation` is **forbidden** from importing
   `sqlmodel` and `sqlalchemy` — one contract with `containers`, as in Stage 8, so it covers a
   module that does not exist yet. This is what makes the stage self-verifying: the goal at the top
   of this file is restated as a rule CI enforces, rather than a thing to remember at review time.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                        # presentation-forbids-sqlmodel now active
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

grep -rn "session.exec\|select(\|Session" app/modules/*/presentation/
# no hits

curl -s localhost:8000/v1/catalog | jq -S . | diff /tmp/catalog.before.json -
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . | diff /tmp/platform.before.json -
```

The N+1 fix needs a check that survives the next refactor, so assert it rather than eyeballing a
log. Add `tests/modules/catalog/test_catalog_queries.py`, counting statements with a SQLAlchemy
`before_cursor_execute` listener on `engine`, and seed a fourth platform inside the test: the count
must not move.

```python
count = 0

@event.listens_for(engine, "before_cursor_execute")
def _count(*_args, **_kwargs):
    nonlocal count
    count += 1
```

## Done when

No module's `presentation/` names a persistence type, `GET /v1/catalog` issues a constant number of
queries regardless of how many platforms are seeded, and both golden diffs are still empty.
