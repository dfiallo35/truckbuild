import { describe, expect, it } from "vitest";

import { priceBuild } from "@/lib/pricing";

import { priceablePlatform, pricingCases } from "./fixtures";

/**
 * The TypeScript half of the pricing mirror. `api/tests/test_pricing.py` runs the same cases
 * against the authoritative Python implementation.
 */

describe("priceBuild against the shared fixtures", () => {
  const priceable = pricingCases.filter((c) => c.expected_total_cents !== null);

  it("has cases to run", () => {
    expect(priceable.length).toBeGreaterThan(0);
  });

  it.each(priceable)("$name", (testCase) => {
    const breakdown = priceBuild(priceablePlatform(testCase.platform), testCase.selected);
    expect(breakdown.total_cents).toBe(testCase.expected_total_cents);
  });
});

describe("priceBuild", () => {
  const platform = {
    slug: "p",
    base_price_cents: 10_000,
    options: [
      { slug: "a", price_delta_cents: 1_000 },
      { slug: "b", price_delta_cents: 2_000 },
    ],
  };

  it("returns the base price when nothing is selected", () => {
    expect(priceBuild(platform, [])).toEqual({
      base_price_cents: 10_000,
      option_deltas: {},
      total_cents: 10_000,
    });
  });

  it("sums the deltas of the selected options", () => {
    const breakdown = priceBuild(platform, ["a", "b"]);
    expect(breakdown.total_cents).toBe(13_000);
    expect(breakdown.option_deltas).toEqual({ a: 1_000, b: 2_000 });
  });

  it("ignores options that are not selected", () => {
    expect(priceBuild(platform, ["a"]).total_cents).toBe(11_000);
  });

  it("rejects a slug the platform does not have", () => {
    expect(() => priceBuild(platform, ["not-a-real-option"])).toThrow(/not-a-real-option/);
  });
});
