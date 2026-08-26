# Stage 6 — Admin and cache revalidation

**Goal:** sales can read submitted builds, and catalog edits reach the public site without a redeploy.

**Prerequisite:** Stage 5 checkpoint passes.

## Steps

1. **`GET /v1/admin/quotes`** — pagination and filtering, guarded by a bearer `ADMIN_TOKEN` in a FastAPI
   dependency. Note in the code that this is deliberately minimal and that the upgrade path is real user
   accounts once more than a couple of people need access.
2. **`GET /v1/admin/quotes/{ref}`** — full build detail.
3. **`services/revalidate.py`** — POSTs `{tags: [...]}` to the web app's `/api/revalidate` with a shared
   `REVALIDATE_SECRET` whenever catalog rows change. The Next.js route verifies the secret and calls
   `revalidateTag`.
4. **Optional, only if sales asks:** a minimal server-rendered admin list at `/admin` behind middleware.
   Skip it otherwise — email already delivers the lead.

## Checkpoint

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" localhost:8000/v1/admin/quotes   # lists the quote
curl localhost:8000/v1/admin/quotes                                          # 401
```

Then change an option price in Postgres, trigger revalidation, and reload the public platform page — the new
price appears with no redeploy.

## Done when

- The admin endpoints are unreachable without the token.
- A catalog edit is visible publicly within seconds, and the revalidation endpoint rejects a wrong secret.
