import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { parse as parseYaml } from "yaml";

import type { Platform } from "@/lib/contract";
import type { PriceablePlatform } from "@/lib/pricing";
import type { OptionRule, RuleablePlatform } from "@/lib/rules";

/**
 * The Vitest half of the shared pricing fixture (see .claude/skills/pricing-mirror). Both this
 * suite and pytest read `fixtures/pricing-cases.json` at the repo root and the same seed
 * catalog, so a case added on one side fails on the other instead of drifting quietly.
 */

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

type FixtureCase = {
  name: string;
  platform: string;
  selected: string[];
  expected_total_cents: number | null;
  expected_violations: {
    kind: "requires" | "excludes";
    option: string;
    needs?: string;
    conflicts_with?: string;
  }[];
};

const catalog = parseYaml(readFileSync(`${REPO_ROOT}/api/seed/catalog.yaml`, "utf8")) as {
  platforms: {
    slug: string;
    base_price_cents: number;
    option_groups: {
      slug: string;
      name: string;
      selection_mode: "single" | "multi";
      required: boolean;
      display_style: "card" | "swatch" | "toggle";
      options: {
        slug: string;
        name: string;
        price_delta_cents: number;
        description?: string;
        swatch?: { url: string; alt_text: string };
      }[];
    }[];
  }[];
  rules: OptionRule[];
};

export const pricingCases: FixtureCase[] = JSON.parse(
  readFileSync(`${REPO_ROOT}/fixtures/pricing-cases.json`, "utf8"),
).cases;

function seedPlatform(slug: string) {
  const platform = catalog.platforms.find((p) => p.slug === slug);
  if (!platform) throw new Error(`no platform with slug ${slug}`);
  return platform;
}

export function priceablePlatform(slug: string): PriceablePlatform {
  const platform = seedPlatform(slug);
  return {
    slug: platform.slug,
    base_price_cents: platform.base_price_cents,
    options: platform.option_groups.flatMap((group) =>
      group.options.map((option) => ({
        slug: option.slug,
        price_delta_cents: option.price_delta_cents,
      })),
    ),
  };
}

export function ruleablePlatform(slug: string): RuleablePlatform {
  const platform = seedPlatform(slug);
  const owned = new Set(
    platform.option_groups.flatMap((group) => group.options.map((option) => option.slug)),
  );
  // Rules live at the top level of the seed and apply to whichever options they name; a
  // platform only sees the ones whose subject it actually has. Mirrors tests/conftest.py.
  return { slug, rules: catalog.rules.filter((rule) => owned.has(rule.subject)) };
}

/** The seed catalog shaped the way `GET /v1/platforms/{slug}` returns it. */
export function apiPlatform(slug: string): Platform {
  const platform = seedPlatform(slug);
  return {
    slug: platform.slug,
    name: slug,
    purpose: "",
    chassis_basis: "",
    base_price_cents: platform.base_price_cents,
    spec_highlights: [],
    standard_equipment: [],
    hero_image: null,
    gallery: [],
    model: null,
    option_groups: platform.option_groups.map((group) => ({
      slug: group.slug,
      name: group.name,
      selection_mode: group.selection_mode,
      required: group.required,
      display_style: group.display_style,
      options: group.options.map((option) => ({
        slug: option.slug,
        name: option.name,
        price_delta_cents: option.price_delta_cents,
        description: option.description ?? "",
        swatch: option.swatch
          ? { kind: "thumbnail" as const, url: option.swatch.url, alt_text: option.swatch.alt_text }
          : null,
        model_effect: null,
      })),
    })),
    rules: ruleablePlatform(slug).rules,
  };
}
