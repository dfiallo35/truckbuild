# Stage 5 — Quote pipeline

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
