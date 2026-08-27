import { describe, expect, it } from "vitest";

import { validateSelection } from "@/lib/rules";

import { pricingCases, ruleablePlatform } from "./fixtures";

/**
 * The TypeScript half of the rules mirror. `api/tests/test_rules.py` runs the same cases
 * against the authoritative Python implementation.
 */

describe("validateSelection against the shared fixtures", () => {
  it.each(pricingCases)("$name", (testCase) => {
    const violations = validateSelection(ruleablePlatform(testCase.platform), testCase.selected);

    expect(violations).toHaveLength(testCase.expected_violations.length);
    testCase.expected_violations.forEach((expected, i) => {
      expect(violations[i].kind).toBe(expected.kind);
      expect(violations[i].option).toBe(expected.option);
      expect(violations[i].needs).toBe(expected.needs ?? null);
      expect(violations[i].conflicts_with).toBe(expected.conflicts_with ?? null);
    });
  });

  it("covers both sides of every seeded rule", () => {
    // A rule with only a passing case is half-tested; the fixture has to fail it too.
    const violated = new Set(
      pricingCases.flatMap((c) => c.expected_violations.map((v) => `${v.kind}:${v.option}`)),
    );
    for (const rule of ruleablePlatform("bristlecone").rules) {
      expect(violated).toContain(`${rule.relation}:${rule.subject}`);
    }
  });
});

describe("validateSelection", () => {
  const platform = {
    slug: "p",
    rules: [
      { subject: "winch", relation: "requires" as const, object: "bumper" },
      { subject: "tent", relation: "excludes" as const, object: "solar" },
    ],
  };

  it("is quiet when nothing is selected", () => {
    expect(validateSelection(platform, [])).toEqual([]);
  });

  it("flags a requires rule whose object is missing", () => {
    expect(validateSelection(platform, ["winch"])).toEqual([
      { kind: "requires", option: "winch", needs: "bumper", conflicts_with: null },
    ]);
  });

  it("is satisfied once the required option is selected", () => {
    expect(validateSelection(platform, ["winch", "bumper"])).toEqual([]);
  });

  it("flags an excludes rule when both options are selected", () => {
    expect(validateSelection(platform, ["tent", "solar"])).toEqual([
      { kind: "excludes", option: "tent", needs: null, conflicts_with: "solar" },
    ]);
  });

  it("does not fire an excludes rule on the object alone", () => {
    expect(validateSelection(platform, ["solar"])).toEqual([]);
  });
});
