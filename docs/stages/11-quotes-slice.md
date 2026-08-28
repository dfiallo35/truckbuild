# Stage 11 — `quotes` becomes a slice

> **Status: complete.**

**Goal:** `POST /v1/quotes` and `POST /v1/enquiries` each become a router that parses a request,
calls one use case, and renders the result. The 340-line module that currently guards for spam,
queries Postgres, validates a selection, prices a build, constructs an aggregate, commits with a
retry loop, sends mail, and shapes a response becomes four files that each do one of those things.

This is the stage with the most behaviour in it, so it moves the pieces one at a time behind an
unchanged wire contract — and it is the first one where the layered shape buys something a reviewer
can name: `submit_quote` gets a test that runs with no Postgres.

**Prerequisite:** Stage 10 checkpoint passes.

## The target slice

```
app/modules/quotes/
├── domain/
│   ├── models.py            Quote · QuoteLine            (pydantic)
│   ├── interfaces.py        IQuoteRepository
│   ├── filters.py           QuoteFilter — ref_eq · kind_eq · platform_slug_eq · search
│   ├── exceptions.py        RejectedSubmissionError(422) · RateLimitedError(429)
│   │                        InvalidSelectionError(422) · UnknownPlatformError(404)
│   │                        QuoteNotFoundError(404)
│   ├── selection.py         structural violations — required, cardinality, duplicates, unknown
│   │                        plus the rule check, with slugs resolved to option names
│   ├── enums.py             QuoteKind · QuoteUseCaseEnum
│   ├── refs.py              new_ref                      (unchanged)
│   └── spam.py              screen                       (unchanged)
├── application/
│   ├── dtos.py              QuoteCreateRequest · EnquiryCreateRequest · QuoteOutput · QuoteDetailOutput
│   ├── interfaces.py        IMailer
│   ├── mappers.py           QuoteMapper — domain ↔ DTO, and the one aggregate builder
│   ├── use_cases.py         SubmitLeadUseCase · SubmitQuoteUseCase · SubmitEnquiryUseCase
│   └── services.py          QuoteService(BaseService)
├── infrastructure/
│   ├── postgres/
│   │   ├── tables.py        QuoteTable · QuoteLineTable
│   │   ├── mappers.py       table ↔ domain
│   │   └── repositories.py  QuoteRepositoryPostgres — owns the ref-collision retry
│   └── mail.py              ResendMailer(IMailer)        ← mail.py, now behind a port
├── dependencies.py          session → repository, settings → mailer + rate limiter → service
└── presentation/
    ├── quotes_api.py        ← router.py, minus everything above
    └── routes.py
```

Four things ended up somewhere other than the sketch above, each for a reason worth keeping:

- **`IMailer` is in `application/`, not `domain/`.** It speaks in `QuoteDetailOutput` — the lead
  summary a use case produced, which is what step 5 asks for — and a `domain` port may not name an
  `application` type. Putting the port beside the shape it speaks in is what actually fixes the
  inversion; putting it one layer down would only have moved the violation.
- **`dependencies.py` sits beside the four layers**, as `catalog`'s and `core/config.py` do, not
  inside `presentation/`. It is the one file that has to see an adapter and an inner layer at once,
  and a file that is the exception to a rule does not belong inside the thing the rule is about.
- **`UnknownPlatformError` joined the list.** `POST /v1/quotes` has always answered a bad
  `platform_slug` with a 404 whose body names the field; that is a rejection, and it needed an
  exception of its own rather than a router branch.
- **`presentation/schemas.py` is gone rather than trimmed.** The request models *are*
  `QuoteCreateRequest` and `EnquiryCreateRequest` in `application/dtos.py`, for the reason
  `core/application/dtos.py` gives about the error body: they are the wire contract, they are pure
  pydantic, and FastAPI is free to parse them at the edge. Their OpenAPI component names moved with
  them (`QuoteCreate` → `QuoteCreateRequest`, `QuoteOut` → `QuoteOutput`, `QuoteDetail` →
  `QuoteDetailOutput`); no request or response *body* changed.

## Steps

1. **Split the entities**, as in Stage 10: `Quote` / `QuoteLine` as pydantic in `domain/models.py`,
   `QuoteTable` / `QuoteLineTable` as SQLModel with explicit `__tablename__`, a mapper between.
   The snapshot rule survives the split unchanged and is worth restating in the entity's docstring:
   a `QuoteLine` copies the option's name and price rather than reading them through `option_id`,
   because a quote is a record of what was offered on a date.

2. **Domain violations stop being HTTP payloads.** `_structural_errors` is pure domain logic —
   required groups, single-select cardinality, duplicates, unknown slugs — that today returns
   `FieldError`, a fragment of a response body. It moves to `domain/selection.py` and returns
   violation types declared beside it, which know nothing about status codes or field names.

   `_rule_errors` splits in *three*, not two. The check itself is already `catalog`'s
   `validate_selection`. Resolving a slug to the name a person would recognise is a fact about the
   catalog, so it sits beside the structural checks in `domain/selection.py` — the router should
   not have to go looking for an option's name. Only the sentence — *"12,000 lb Winch needs the
   Heavy-Duty Winch Bumper."*, *"cannot be fitted with"* — is presentation, and it is
   `_sentence()` in `presentation/quotes_api.py` beside the violation → `FieldError` mapping.
   Wording a customer reads belongs where the rest of the wording lives.

3. **The repository owns the write.** `_save` — its `session.commit()`, its `rollback` on
   `IntegrityError`, and its `REF_ATTEMPTS` retry — becomes
   `QuoteRepositoryPostgres.create(quote)`. The unique index on `quote.ref` is a storage fact and
   the retry is how storage copes with it; neither is the use case's business.

4. **Two use cases, ports as constructor arguments.** `SubmitQuoteUseCase` overrides `validate`
   (structural violations, then rules — in that order, because reporting both at once would explain
   a conflict with an option that does not exist) and returns the persisted quote.
   `SubmitEnquiryUseCase` is the same pipeline with no build to price. Both extend a shared
   `SubmitLeadUseCase(CreateUseCase)` holding the screen-limit-look-up-store spine, and the
   `Quote`/`QuoteLine` aggregate construction previously written twice in the router is written
   once, in the mapper.

   **`exec` is overridden, which CLAUDE.md's "override a hook, never `exec`" rule allows for and
   which is worth stating the reason for.** `CreateUseCase.exec` maps the request to an entity
   *before* `validate` runs, and a quote cannot be built before its selection has been judged —
   pricing a selection naming an option the platform does not have raises `ValueError`, which is a
   500 rather than the 422 that fault deserves. So the entity is built inside `run`, and the order
   the template exists to fix, `pre_run → validate → run → post_run`, is exactly the order the
   override reads in.

   Neither use case names a `Response`, a status code, or a header. Rejections are raised as the
   `domain/exceptions.py` errors above. `rejected` and `rate_limited` are rendered by the handler
   `core` already installs, with no code in this module at all — which needed one small addition to
   the kernel: `BaseError` now carries optional `headers`, because a 429 has to say how long to
   wait and how long is the rate limiter's answer, long out of scope by the time the handler runs.
   `invalid_selection` and `unknown_platform` are rendered by the router, because their bodies
   carry an `errors[]` array of per-field sentences and the core handler cannot express one. Their
   status, code and headline still come off the exception; only the prose is decided at the edge.

5. **`IMailer` and `IRateLimiter` become injected.**

   `infrastructure/mail.py` implements `IMailer` as `ResendMailer`, taking an *application-level
   lead summary* — `QuoteDetailOutput` — rather than `QuoteDetail`. The mail adapter used to import
   a response schema, so an outbound adapter depended on the shape of an HTTP body; that is the
   inversion this fixes, and it was one of the two named `ignore_imports` in `pyproject.toml`. Both
   came out this stage, and so did the third.

   The port itself lives in `application/interfaces.py` rather than beside `IQuoteRepository`, for
   the reason given above the tree: it speaks in an `application` DTO, and a `domain` port may not
   name one.

   The router used to build a process-global `RateLimiter` at import time from `get_settings()`,
   bypassing dependency injection entirely — which is why `test_quotes_api.py` had to import that
   global and reset it between tests. It is supplied through `dependencies.py` as `IRateLimiter`.
   It is *still* process-global, and has to be: one rebuilt per request would count to one and
   never reach its limit. What changed is that it is injected rather than reached for, so the
   fixture is now `app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(...)` — a
   substitution at the composition root rather than a reach into another module's state.

   This does **not** fix the limiter being per-instance on serverless, which
   [decisions.md](../decisions.md) records as a known liability. It makes the fix — a shared store —
   a one-file change behind an interface that now exists.

6. **`BackgroundTasks` stays in the router.** Scheduling is a framework capability: the use case
   returns what needs sending, and the router decides when to send it. Handing a use case a
   `BackgroundTasks` would put `fastapi` back in an application layer for the sake of one line.

   The rule it protects stays too, and belongs in the router's docstring: **a saved lead beats a
   perfect response.** Once the row is committed the request has succeeded; mail goes out in a task
   that swallows its own failures.

7. **`_client_ip` stays in the router.** Reading `X-Forwarded-For` is HTTP, and the reason it is
   trusted — the browser never reaches this API directly — is an HTTP-layer fact. The use case is
   handed an address, not a `Request`.

8. **Widen the two contracts** from Stage 10 to cover `app.modules.quotes.domain` and
   `app.modules.quotes.presentation`, and **delete both `ignore_imports`** from the
   `Layers within every module` contract. That list should only ever shrink; this stage empties it.

   **The third one came out here too, and had to.** `admin` read leads with `select(Quote)` against
   what were `quotes`' domain entities — a legal import while the tables lived in `domain/`. Moving
   them to `infrastructure/postgres/` in step 1 makes that import a facade violation, so this stage
   either grew the exception list or moved `admin` off direct table access. It moved `admin`:
   its router now declares an `IQuoteRepository` port, builds a `QuoteFilter`, and composes no
   query. `QuoteFilter`'s `ref_eq` / `kind_eq` / `platform_slug_eq` / `search` fields and the
   `_escape_like` + `created_at DESC, id DESC` policy behind them — Stage 12's step 1 — are here
   because this stage's own target slice named those fields, and fields with no repository behind
   them would have been a lie.

   Stage 12 keeps its own work: `admin`'s use cases, its output DTOs, its
   `presentation/filters.py`, and landing the full contract set. Its wire bodies did not move.

9. **The first tests with no database.** `tests/modules/quotes/test_submit_quote.py` exercises the
   use cases against a fake `IQuoteRepository`, a fake `IRateLimiter` and a fake catalog read. No
   fake `IMailer` is needed: mail is scheduled by the router, so a use case never touches one —
   which is step 6 showing up as something a test does not have to do.

   The existing database-backed API tests all **stay**. They are the contract tests proving the wire
   shape did not move, and replacing them with faster fakes would trade away the only thing checking
   that.

## Checkpoint

```bash
cd api
uv run ruff check . && uv run ruff format --check .
uv run lint-imports                        # both ignore_imports gone
uv run alembic upgrade head
uv run python -m app.seed --no-revalidate
uv run pytest -q

grep -rnE "HTTPException|Response|(from|import) (fastapi|starlette|sqlmodel|sqlalchemy)" \
  app/modules/quotes/domain/ app/modules/quotes/application/
# docstrings only — neither layer owes anything to HTTP or to storage
#
# Narrower than the `status_code` this originally grepped for, deliberately. `status_code = 422`
# on a `BaseError` subclass is the kernel's own mechanism (see core/domain/exceptions.py) and is
# precisely how Stage 9 arranged for domain code to stop importing `HTTPException` — grepping for
# it would fail the check on the thing the check exists to encourage. `lint-imports` enforces the
# import half from CI either way.

uv run pytest tests/modules/quotes/test_submit_quote.py -q -p no:cacheprovider
# passes with DATABASE_URL unset
```

Then the flow that crosses every boundary, end to end:

```bash
cd ../web && pnpm e2e
```

A submitted build must still come back with a server-computed total, a `ref`, and a confirmation
mail logged — and a build with an excluded pair must still come back 422 with the same prose in the
same field.

## Done when

`submit_quote` has a test that runs with `DATABASE_URL` unset, no file under `quotes/domain/` or
`quotes/application/` names an ORM or a web framework, `pyproject.toml` has no pinned import
exceptions left, and `pnpm e2e` is green against the running API.

## Result

All of it, against the local stack:

- `ruff check` and `ruff format --check` clean; **10 contracts kept, 0 broken**, and
  `grep -n ignore_imports pyproject.toml` finds nothing.
- `pytest -q` — **151 passed**, of which 13 are the new
  `tests/modules/quotes/test_submit_quote.py`, green with `DATABASE_URL` unset.
- `alembic revision --autogenerate` writes an **empty migration**: `Quote` → `QuoteTable` and
  `QuoteLine` → `QuoteLineTable` moved package *and* class name without moving a table, which is
  what the pinned `__tablename__` is for. `tests/test_entity_registry.py` now holds all seven
  table names still.
- Both golden captures diff clean, and every lead body was checked against the running API by hand:
  the 201, the `invalid_selection` 422 (same prose, same `field`, same `code`), the
  `unknown_platform` 404 with its `errors[]` entry, and the 429 with `Retry-After: 600` on the
  sixth submission from one address. The admin list, detail and 404 bodies are unchanged too.
- `pnpm e2e` — **45 passed, 5 skipped**, the skips being the pre-existing mobile-only cases.

### The one number worth quoting

`presentation/router.py` was 327 lines that guarded for spam, queried Postgres, validated a
selection, priced a build, constructed an aggregate, committed with a retry loop, sent mail and
shaped a response. `presentation/quotes_api.py` is 170, over half of it docstring and comment: two
handlers, `_client_ip`, three port declarations, and the three functions that turn a violation into
a sentence. Everything else is in a file named after the one thing it does — and `admin`'s router
lost its 64-line query composition on the way past.
