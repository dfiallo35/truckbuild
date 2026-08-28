import { createHash, timingSafeEqual } from "node:crypto";

import { z } from "zod";

/**
 * Everything the `/api/revalidate` webhook decides before it touches the cache: is the caller
 * who it says it is, and are these tags this site actually has.
 *
 * Kept out of the route handler so it can be tested without a running server -- the handler is
 * then only the two lines that call `revalidateTag`. See `api/app/core/revalidate.py` for
 * the caller and .claude/skills/cache-and-revalidation for the contract.
 */

/** `catalog`, or `platform-<slug>`. Anything else is a caller confused about this site. */
const TAG_PATTERN = /^(catalog|platform-[a-z0-9]+(?:-[a-z0-9]+)*)$/;

const MAX_TAGS = 50;

const bodySchema = z.object({
  tags: z.array(z.string().max(120)).min(1).max(MAX_TAGS),
});

export type RevalidationPlan =
  { ok: true; tags: string[] } | { ok: false; status: number; code: string; message: string };

/**
 * Compare without leaking, through the length, how much of the secret was right. Both sides are
 * hashed first because `timingSafeEqual` throws on a length mismatch, which would itself be the
 * leak.
 */
function secretMatches(presented: string, expected: string): boolean {
  const a = createHash("sha256").update(presented).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

function bearerToken(authorization: string | null): string {
  const match = /^Bearer +(.+)$/i.exec(authorization ?? "");
  return match ? match[1].trim() : "";
}

export function planRevalidation(input: {
  authorization: string | null;
  body: unknown;
  secret: string | undefined;
}): RevalidationPlan {
  // Fail closed. An unset secret would otherwise turn this into an open endpoint that lets
  // anyone drop the caches this whole site renders from.
  if (!input.secret) {
    return {
      ok: false,
      status: 500,
      code: "misconfigured",
      message: "REVALIDATE_SECRET is not set on the web app (see .env.example).",
    };
  }

  if (!secretMatches(bearerToken(input.authorization), input.secret)) {
    return {
      ok: false,
      status: 401,
      code: "unauthorized",
      message: "A valid revalidation secret is required.",
    };
  }

  const parsed = bodySchema.safeParse(input.body);
  if (!parsed.success) {
    return {
      ok: false,
      status: 400,
      code: "invalid_body",
      message: `Expected {"tags": [...]} with 1 to ${MAX_TAGS} tags.`,
    };
  }

  const tags = [...new Set(parsed.data.tags)];
  const unknown = tags.filter((tag) => !TAG_PATTERN.test(tag));
  if (unknown.length > 0) {
    // Named rather than dropped: a tag this site does not use means the two sides disagree
    // about what is cached, and silently succeeding would hide that until a price went stale.
    return {
      ok: false,
      status: 400,
      code: "unknown_tag",
      message: `Not a tag this site caches: ${unknown.join(", ")}.`,
    };
  }

  return { ok: true, tags };
}
