# Stage 10 — Use cases: one call per endpoint

> **Status: not started.**

**Goal:** each router function parses a request, calls one use case from its own module, and maps
the result to a response. The business of the service lives in the modules' `application/` layers,
and the full layered contract is green.

This is the stage the previous two were preparation for. It is also the one that can change
behaviour, so it moves the pieces one at a time behind an unchanged wire contract.

**Prerequisite:** Stage 9 checkpoint passes.

## The use cases, by module

| Module | Use cases |
|---|---|
| `catalog` | `get_catalog` · `get_platform` · `seed_catalog` (Stage 11) |
| `quotes` | `submit_quote` · `submit_enquiry` |
| `admin` | `list_quotes` · `get_quote` · `revalidate_catalog` |

`admin` owns no entities and no repository, and its use cases are thin — but they exist, because the
alternative is an admin router calling two other modules' repositories directly, which is exactly
the coupling this migration is removing.

## Steps

1. **Domain violations stop being HTTP payloads.** `_structural_errors` in the quotes router is pure
   domain logic — required groups, single-select cardinality, duplicates, unknown slugs — that
   currently returns `FieldError`, a fragment of an HTTP response body. It moves to
   `quotes/domain/selection.py` and returns violation types declared beside it, which know nothing
   about status codes or field names.

   `_rule_errors` splits in two. The check itself is already `catalog`'s `validate_selection`. The
   customer-facing prose — *"Winch needs the Heavy bumper"*, *"cannot be fitted with"* — is
   presentation, and moves to `quotes/presentation/` beside the violation → `FieldError` mapping.
   Wording a customer reads should live where the rest of the wording lives.
2. **One module per use case, ports as constructor arguments.** Each use case returns a domain
   result or raises a domain error; none of them may name a `Response`, a status code, or a header.
   The `Quote`/`QuoteLine` aggregate construction currently written twice in the quotes router —
   once for a build, once for an enquiry — is written once in `submit_quote`'s module.
3. **Ports for the outbound adapters.** `Mailer` joins `quotes/application/ports.py`;
   `CacheInvalidator` joins `catalog/application/ports.py`, since the catalog is what gets
   invalidated. `quotes/infrastructure/mail.py` and `core/revalidate.py` implement them.

   This fixes a real inversion: `services/mailer.py` imports `QuoteDetail` from the schema layer
   today, so the mail adapter depends on the shape of an HTTP response. The port takes an
   application-level lead summary instead, and the mailer stops caring what the API returns to a
   browser.
4. **The rate limiter becomes injected.** The quotes router builds a process-global `RateLimiter` at
   import time from `get_settings()`, bypassing dependency injection entirely — which is why
   `test_quotes_api.py` has to import that global and reset it between tests. It becomes a port with
   `core/ratelimit.py` as the in-memory implementation, supplied through the module's
   `dependencies.py`, and the test fixture becomes a substitution rather than a reach-in.

   Note this does not fix the limiter being per-instance on serverless, which
   [decisions.md](../decisions.md) records as a known liability. It does make the fix — a shared
   store — a one-file change behind an interface that already exists.
5. **Routers become thin.** `BackgroundTasks` **stays in the router**: scheduling is a framework
   capability, so the use case returns what needs sending and the router decides when to send it.
   The alternative — handing the use case a `BackgroundTasks` — would put `fastapi` back in an
   application layer for the sake of one line.
6. **Land the full layers contract**, replacing the piecemeal `forbidden` ones from Stages 8 and 9.
   Applied with `containers` across every module:

   ```
   presentation : infrastructure  →  application  →  domain
   ```

   `main.py` and each module's `presentation/dependencies.py` are the composition root and are
   declared as such — the only modules allowed to see across the layer boundary, because something
   has to know how the pieces are assembled.
7. **Add use-case tests with fake ports** — the first tests in this repository that exercise the
   quote pipeline without a live Postgres, sitting in `tests/modules/quotes/`. The existing
   database-backed API tests all stay. They are the contract tests that prove the wire shape did not
   move, and replacing them with faster fakes would trade away the only thing checking that.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                        # full layers contract active
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

grep -rn "FieldError\|status_code\|HTTPException" app/modules/*/domain/ app/modules/*/application/
# no hits — neither layer owes anything to HTTP

curl -s localhost:8000/v1/catalog | jq -S . | diff /tmp/catalog.before.json -
curl -s localhost:8000/v1/platforms/bristlecone | jq -S . | diff /tmp/platform.before.json -
```

Then the one flow that crosses every boundary, from
[architecture.md](../architecture.md#the-request-path-for-a-lead):

```bash
cd web && pnpm e2e
```

## Done when

The full layered contract passes, `submit_quote` has a test that runs with no database, no `domain/`
or `application/` module mentions a status code, and every golden diff is still empty.
