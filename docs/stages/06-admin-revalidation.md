# Stage 6 — Admin and cache revalidation

> **Status: complete.** Checkpoint verified 2026-08-27.

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
   Skip it otherwise — email already delivers the lead. **Skipped** — nobody asked, and the lead email
   still carries the whole build.

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

## Notes from the build

- **`revalidateTag` takes a second argument now.** In Next.js 16 it is `revalidateTag(tag, profile)`;
  calling it with one argument logs a deprecation warning. The webhook passes `{ expire: 0 }` rather
  than the documented-as-recommended `'max'`, because `'max'` keeps serving the cached copy for up to
  five minutes while it refreshes — and this stage's own criterion is that a corrected price is public
  within seconds. `updateTag`, which expires immediately by default, throws in a route handler: it is
  Server Actions only, and the caller here is another service rather than a form.
- **`localhost:3000` from inside the API container is the API container.** Compose now sets
  `WEB_BASE_URL: http://host.docker.internal:3000` with a `host-gateway` alias; before that, every
  revalidation the containerised API sent — including the seed's — posted into the void, which fails in
  exactly the silent way this webhook is most dangerous.
- **A long-running `next dev` does not pick up a newly added route directory.** `src/app/api/revalidate/`
  kept 404ing on a dev server that had been started before the file existed, through a file touch and a
  recompile. Restart the dev server after adding a route segment rather than debugging the handler.
- **The seed revalidates by default and takes `--no-revalidate` to opt out.** Opt-out rather than opt-in
  because a stale public price is the costlier mistake; CI passes the flag, since neither job has a web
  app to tell.
