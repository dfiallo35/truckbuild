import { revalidateTag } from "next/cache";

import { planRevalidation } from "@/lib/revalidate";

/**
 * The other end of `api/app/core/revalidate.py`: FastAPI POSTs `{tags: [...]}` here with the
 * shared `REVALIDATE_SECRET` when catalog rows change, and this drops the matching `use cache`
 * entries so the next request re-reads the catalog.
 *
 * `{ expire: 0 }` rather than the usual `'max'`: that profile keeps serving the cached copy for
 * up to five minutes while it refreshes behind the scenes, and the whole point of this webhook
 * is that a corrected price is public within seconds. `updateTag`, which expires immediately by
 * default, cannot be used -- it is Server Actions only, and this is a route handler because the
 * caller is another service rather than a form.
 */

export async function POST(request: Request): Promise<Response> {
  const body: unknown = await request.json().catch(() => null);

  const plan = planRevalidation({
    authorization: request.headers.get("authorization"),
    body,
    secret: process.env.REVALIDATE_SECRET,
  });

  if (!plan.ok) {
    console.error(`revalidation refused (${plan.code}): ${plan.message}`);
    return Response.json(
      { code: plan.code, message: plan.message },
      { status: plan.status, headers: plan.status === 401 ? { "WWW-Authenticate": "Bearer" } : {} },
    );
  }

  for (const tag of plan.tags) {
    revalidateTag(tag, { expire: 0 });
  }
  console.log(`revalidated cache tags: ${plan.tags.join(", ")}`);

  return Response.json({ revalidated: plan.tags, now: Date.now() });
}
