# Stage 11 — `quotes` becomes a slice

> **Status: not started.**

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
│   ├── interfaces.py        IQuoteRepository · IMailer
│   ├── filters.py           QuoteFilter — ref_eq · kind_eq · platform_slug_eq · search
│   ├── exceptions.py        RejectedSubmissionError(422) · RateLimitedError(429)
│   │                        InvalidSelectionError(422) · QuoteNotFoundError(404)
│   ├── selection.py         structural violations — required, cardinality, duplicates, unknown
│   ├── enums.py             QuoteKind                    (unchanged)
│   ├── refs.py              new_ref                      (unchanged)
│   └── spam.py              screen                       (unchanged)
├── application/
│   ├── dtos.py              QuoteCreateRequest · EnquiryCreateRequest · QuoteOutput · QuoteDetailOutput
│   ├── mappers.py           QuoteMapper — domain ↔ DTO
│   ├── use_cases.py         SubmitQuoteUseCase · SubmitEnquiryUseCase
│   └── services.py          QuoteService(BaseService)
├── infrastructure/
│   ├── postgres/
│   │   ├── tables.py        QuoteTable · QuoteLineTable
│   │   ├── mappers.py       table ↔ domain
│   │   └── repositories.py  QuoteRepositoryPostgres — owns the ref-collision retry
│   └── mail.py              SmtpMailer(IMailer)          ← mail.py, now behind a port
└── presentation/
    ├── quotes_api.py        ← router.py, minus everything above
    ├── dependencies.py      session → repository, settings → mailer + rate limiter → service
    └── routes.py
```

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

   `_rule_errors` splits in two. The check itself is already `catalog`'s `validate_selection`. The
   customer-facing prose — *"Winch needs the Heavy bumper"*, *"cannot be fitted with"* — is
   presentation, and moves to `presentation/quotes_api.py` beside the violation → `FieldError`
   mapping. Wording a customer reads belongs where the rest of the wording lives.

3. **The repository owns the write.** `_save` — its `session.commit()`, its `rollback` on
   `IntegrityError`, and its `REF_ATTEMPTS` retry — becomes
   `QuoteRepositoryPostgres.create(quote)`. The unique index on `quote.ref` is a storage fact and
   the retry is how storage copes with it; neither is the use case's business.

4. **Two use cases, ports as constructor arguments.** `SubmitQuoteUseCase(CreateUseCase)` overrides
   `validate` (structural violations, then rules — in that order, because reporting both at once
   would explain a conflict with an option that does not exist) and returns the persisted quote.
   `SubmitEnquiryUseCase(CreateUseCase)` is the same pipeline with no build to price. The
   `Quote`/`QuoteLine` aggregate construction currently written twice in the router is written once,
   in the mapper.

   Neither use case may name a `Response`, a status code, or a header. Rejections are raised as the
   `domain/exceptions.py` errors above and rendered by the handler `core` already installs.

5. **`IMailer` and `IRateLimiter` become injected.**

   `infrastructure/mail.py` implements `IMailer`, taking an *application-level lead summary* rather
   than `QuoteDetail`. Today the mail adapter imports a response schema, so an outbound adapter
   depends on the shape of an HTTP body — that is the inversion this fixes, and it is one of the
   two named `ignore_imports` in `pyproject.toml`. Both come out this stage.

   The router currently builds a process-global `RateLimiter` at import time from `get_settings()`,
   bypassing dependency injection entirely — which is why `test_quotes_api.py` has to import that
   global and reset it between tests. It is supplied through `dependencies.py` as `IRateLimiter`,
   and the fixture becomes a substitution rather than a reach-in.

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

9. **The first tests with no database.** `tests/modules/quotes/test_submit_quote.py` exercises the
   use case against a fake `IQuoteRepository`, a fake `IMailer`, and a fake `IRateLimiter`.

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

grep -rn "sqlmodel\|sqlalchemy\|fastapi\|status_code\|HTTPException" \
  app/modules/quotes/domain/ app/modules/quotes/application/
# no hits — neither layer owes anything to HTTP or to storage

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
`quotes/application/` mentions a status code or an ORM, `pyproject.toml` has no `ignore_imports`
left, and `pnpm e2e` is green against the running API.
