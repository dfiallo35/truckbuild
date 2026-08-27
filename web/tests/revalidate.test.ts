import { describe, expect, it } from "vitest";

import { planRevalidation } from "@/lib/revalidate";

/**
 * The gate in front of the cache-busting webhook. This route is public -- FastAPI reaches it
 * over the internet -- and everything the marketing site renders comes out of the caches it can
 * drop, so "rejects the wrong caller" is the whole point of the file it tests.
 */

const SECRET = "dev-revalidate-secret";

function plan(overrides: Partial<Parameters<typeof planRevalidation>[0]> = {}) {
  return planRevalidation({
    authorization: `Bearer ${SECRET}`,
    body: { tags: ["catalog"] },
    secret: SECRET,
    ...overrides,
  });
}

describe("authorization", () => {
  it("accepts the shared secret as a bearer token", () => {
    expect(plan()).toEqual({ ok: true, tags: ["catalog"] });
  });

  it("refuses a request with no authorization at all", () => {
    expect(plan({ authorization: null })).toMatchObject({ ok: false, status: 401 });
  });

  it("refuses a wrong secret", () => {
    expect(plan({ authorization: "Bearer nope" })).toMatchObject({ ok: false, status: 401 });
  });

  it("refuses a secret that is merely a prefix of the real one", () => {
    expect(plan({ authorization: `Bearer ${SECRET.slice(0, -1)}` })).toMatchObject({
      ok: false,
      status: 401,
    });
  });

  it("refuses a bare token sent without the Bearer scheme", () => {
    expect(plan({ authorization: SECRET })).toMatchObject({ ok: false, status: 401 });
  });

  it("fails closed when the web app has no secret configured", () => {
    // Otherwise an unset secret on either side would leave this endpoint open to anyone who
    // wanted to drop every cache on the site, repeatedly.
    expect(plan({ secret: undefined, authorization: "Bearer " })).toMatchObject({
      ok: false,
      status: 500,
      code: "misconfigured",
    });
    expect(plan({ secret: "", authorization: null })).toMatchObject({ ok: false, status: 500 });
  });
});

describe("tags", () => {
  it("takes both tiers of tag", () => {
    const result = plan({ body: { tags: ["catalog", "platform-bristlecone"] } });
    expect(result).toEqual({ ok: true, tags: ["catalog", "platform-bristlecone"] });
  });

  it("drops a repeat rather than expiring the same tag twice", () => {
    expect(plan({ body: { tags: ["catalog", "catalog"] } })).toEqual({
      ok: true,
      tags: ["catalog"],
    });
  });

  it("names a tag this site does not cache instead of silently ignoring it", () => {
    const result = plan({ body: { tags: ["catalog", "platfrom-bristlecone"] } });
    expect(result).toMatchObject({ ok: false, status: 400, code: "unknown_tag" });
    expect(result.ok === false && result.message).toContain("platfrom-bristlecone");
  });

  it.each([
    ["a body that is not an object", null],
    ["a body with no tags", {}],
    ["an empty tag list", { tags: [] }],
    ["tags that are not strings", { tags: [{ tag: "catalog" }] }],
    ["more tags than this site has", { tags: Array.from({ length: 51 }, () => "catalog") }],
  ])("refuses %s", (_label, body) => {
    expect(plan({ body })).toMatchObject({ ok: false, status: 400 });
  });
});
