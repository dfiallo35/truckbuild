# Stage 5 — Quote pipeline

> **Status: complete.** Checkpoint verified 2026-08-27.

**Goal:** a finished build becomes a stored, server-priced lead that reaches sales.

**Prerequisite:** Stage 4 checkpoint passes.

## Steps

1. **`POST /v1/quotes`** accepts
   `{platform_slug, option_slugs[], contact{}, intended_use, timeline, notes}`. It **re-validates the
   selection and recomputes the price server-side, ignoring any client-supplied total** — a client-submitted
   price is user input, not a fact. Invalid combinations are rejected with per-rule errors. On success it
   persists `Quote` + `QuoteLine` and returns a reference number.
2. **`services/mailer.py`** sends a formatted build summary to `SALES_INBOX` and a confirmation to the
   customer (Resend via `httpx`). Email failure is logged but does **not** fail the request — the lead is
   already saved, and losing it to a transient mail problem is the worse outcome.
3. **Spam controls** — rate-limit by IP, plus a honeypot field and a minimum time-to-submit check.
4. **Front end form** — in a modal or at `/configurator/[slug]/request`, submitted through a Next.js
   **Server Action** that proxies to FastAPI, so `API_BASE_URL` and any secret never reach the browser.
   Render field-level validation errors returned by the API.
5. **`/thank-you`** — confirmation page showing the reference number and next steps.
6. **Wire `/contact`** to the same backend as a general, non-build enquiry.

## Checkpoint

```bash
# submit a build through the UI, then:
docker compose exec api psql $DATABASE_URL -c "select ref, total_cents from quote"
```

The stored total must match what the UI displayed. Then re-POST the same payload with a tampered
`total_cents` and confirm the server stores its own computed price regardless.

## Done when

- A submitted build appears in Postgres with a server-computed price.
- Sales receives the summary email and the customer receives a confirmation.
- Breaking the mail provider's API key still results in a saved lead.

## Notes from the build

- **One `quote` table with a `kind` discriminator**, not a separate `enquiry` table. A build
  request and a /contact enquiry differ only in whether a build is attached, and sales wants one
  list of leads and one series of reference numbers, so the platform and price columns are simply
  null for an enquiry.
- **`QuoteLine` copies the option's name and price** instead of reading them through
  `option_id`. A quote records what was offered on a date; repricing the catalog next quarter must
  not silently rewrite a quote sent last quarter.
- **`QuoteCreate` has no price field at all.** Ignoring a submitted total would be enough, but not
  accepting one says the same thing in the type. `extra="ignore"` drops a tampered `total_cents`,
  and a contract test posts one to prove the stored total is still the server's.
- **Every rejection shares one shape** — `{code, message, errors[{field, message, code}]}` — and
  FastAPI's own 422 is reshaped into it by an exception handler (`app/errors.py`). The web form
  renders errors beside the input at fault, which it could only do with a single body to parse.
  The API names the payload path (`contact.email`); the front end drops the `contact.` prefix so
  the key matches the input's name.
- **Selection errors have no field to appear beside**, since the build is a hidden input rather
  than something the customer typed. They render in the same "Resolve before sending" notice as
  the client-side rule violations, which is where someone is already looking.
- **Structural validation lives in the router, not in `services/rules.py`.** Two options in a
  single-select group and an empty required group are catalog-structure problems, not compatibility
  rules; putting them in the pure module would have forced a mirror change in TypeScript for a
  check `web/src/lib/build.ts` already enforces by repairing the URL.
- **The rate limiter keys on the forwarded address, not the socket peer.** Every submission
  arrives from the Next.js server, so without `X-Forwarded-For` every visitor would share one
  bucket. That is safe only while the web app is the only route in; exposing the API publicly
  would make the header spoofable and the socket peer the honest key.
- **Spam controls are heuristics and stay generous.** A honeypot field and a minimum
  time-to-submit, both of which a determined script can defeat. The rejection message never names
  the control that fired — that would tell an automated submitter what to change.
- **Mail is best-effort by construction.** `send_lead_emails` swallows and logs its own failures
  and runs in a background task, so a dead provider costs a confirmation email, never the lead.
  With no `RESEND_API_KEY` the rendered message goes to the log instead, which is also how the copy
  gets reviewed without sending anything. Uvicorn configures only its own loggers, so `app/main.py`
  now calls `logging.basicConfig` — without it those INFO lines went nowhere.
- **A native `<dialog>` holds the top layer until it is closed.** Navigating out of the build sheet
  with a `<Link>` left the request page rendered behind a backdrop that swallowed every click; the
  link now closes the dialog on the way out.
