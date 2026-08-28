/**
 * Build pricing, mirroring `api/app/modules/catalog/domain/pricing.py`.
 *
 * This half exists only so the configurator's price updates the instant an option is clicked.
 * The Python half is authoritative: `POST /v1/quotes` recomputes the total from the slugs and
 * ignores anything the browser says it should be. Both are held to
 * `fixtures/pricing-cases.json` -- see .claude/skills/pricing-mirror.
 *
 * Field names stay snake_case to match the Python dataclasses and the wire format, so a case
 * can be compared field-for-field across the two suites without a translation layer in between.
 */

export type PriceableOption = {
  slug: string;
  price_delta_cents: number;
};

export type PriceablePlatform = {
  slug: string;
  base_price_cents: number;
  options: PriceableOption[];
};

export type PriceBreakdown = {
  base_price_cents: number;
  option_deltas: Record<string, number>;
  total_cents: number;
};

/**
 * Sum the platform base price and the price delta of every selected option.
 *
 * Throws if a selected slug does not belong to the platform -- a build referencing an option
 * that does not exist is malformed input, not a zero-cost no-op.
 */
export function priceBuild(
  platform: PriceablePlatform,
  selectedOptionSlugs: string[],
): PriceBreakdown {
  const deltasBySlug = new Map(platform.options.map((o) => [o.slug, o.price_delta_cents]));

  const unknown = selectedOptionSlugs.filter((slug) => !deltasBySlug.has(slug));
  if (unknown.length > 0) {
    throw new Error(
      `platform '${platform.slug}' has no option(s): ${[...unknown].sort().join(", ")}`,
    );
  }

  const option_deltas: Record<string, number> = {};
  for (const slug of selectedOptionSlugs) {
    option_deltas[slug] = deltasBySlug.get(slug)!;
  }

  const total_cents =
    platform.base_price_cents + Object.values(option_deltas).reduce((sum, d) => sum + d, 0);

  return { base_price_cents: platform.base_price_cents, option_deltas, total_cents };
}
