import type { Option, OptionGroup, Platform } from "@/lib/contract";
import type { PriceablePlatform } from "@/lib/pricing";
import type { RuleablePlatform } from "@/lib/rules";

/**
 * A build is a platform plus a set of selected option slugs, and it lives in the URL query
 * string (`?o=slug-a,slug-b`). That is what makes a build shareable, refresh-safe and free of
 * any database round trip -- see docs/stages/04-configurator.md.
 *
 * Everything here treats the query string as untrusted: it may name an option that was renamed
 * last quarter, two options from the same single-select group, or nothing at all. A shared URL
 * outlives the catalog it was built from, so decoding repairs rather than throws.
 */

export const BUILD_PARAM = "o";

export function allOptions(platform: Platform): Option[] {
  return platform.option_groups.flatMap((group) => group.options);
}

export function optionBySlug(platform: Platform): Map<string, Option> {
  return new Map(allOptions(platform).map((option) => [option.slug, option]));
}

export function groupOf(platform: Platform, slug: string): OptionGroup | undefined {
  return platform.option_groups.find((group) =>
    group.options.some((option) => option.slug === slug),
  );
}

/** Catalog order, so the same set of options always encodes to the same string. */
function canonical(platform: Platform, selected: Iterable<string>): string[] {
  const chosen = new Set(selected);
  return allOptions(platform)
    .map((option) => option.slug)
    .filter((slug) => chosen.has(slug));
}

/** Required groups start on their first option; optional groups start empty. */
export function defaultSelection(platform: Platform): string[] {
  return platform.option_groups
    .filter((group) => group.required && group.options.length > 0)
    .map((group) => group.options[0].slug);
}

export function encodeSelection(platform: Platform, selected: string[]): string {
  return canonical(platform, selected).join(",");
}

/**
 * Read a selection out of the query string, repairing whatever the URL got wrong: unknown
 * slugs are dropped, a single-select group keeps only its first named option, and a required
 * group nobody mentioned falls back to its default.
 *
 * A selection that breaks a compatibility rule is deliberately kept -- the configurator
 * explains the conflict inline, which it cannot do for a choice it silently threw away.
 */
export function decodeSelection(platform: Platform, raw: string | null | undefined): string[] {
  const known = optionBySlug(platform);
  const named = (raw ?? "")
    .split(",")
    .map((slug) => slug.trim())
    .filter((slug) => slug.length > 0 && known.has(slug));

  const selected = new Set<string>();
  const claimedSingleGroups = new Set<string>();

  for (const slug of named) {
    const group = groupOf(platform, slug);
    if (!group) continue;
    if (group.selection_mode === "single") {
      if (claimedSingleGroups.has(group.slug)) continue;
      claimedSingleGroups.add(group.slug);
    }
    selected.add(slug);
  }

  for (const group of platform.option_groups) {
    if (!group.required || group.options.length === 0) continue;
    const filled = group.options.some((option) => selected.has(option.slug));
    if (!filled) selected.add(group.options[0].slug);
  }

  return canonical(platform, selected);
}

/**
 * Select or clear one option. Single-select groups swap their choice; a required one cannot be
 * emptied, since a build with no cab is not a build. Multi-select groups toggle.
 */
export function toggleOption(platform: Platform, selected: string[], slug: string): string[] {
  const group = groupOf(platform, slug);
  if (!group) return selected;

  const next = new Set(selected);

  if (group.selection_mode === "single") {
    if (next.has(slug)) {
      if (group.required) return canonical(platform, next);
      next.delete(slug);
      return canonical(platform, next);
    }
    for (const option of group.options) next.delete(option.slug);
    next.add(slug);
    return canonical(platform, next);
  }

  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  return canonical(platform, next);
}

/** The platform reshaped for the pure pricing mirror. */
export function toPriceable(platform: Platform): PriceablePlatform {
  return {
    slug: platform.slug,
    base_price_cents: platform.base_price_cents,
    options: allOptions(platform).map((option) => ({
      slug: option.slug,
      price_delta_cents: option.price_delta_cents,
    })),
  };
}

/** The platform reshaped for the pure rules mirror. */
export function toRuleable(platform: Platform): RuleablePlatform {
  return { slug: platform.slug, rules: platform.rules };
}
