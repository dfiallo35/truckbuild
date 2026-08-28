/**
 * Option compatibility rules, mirroring `api/app/modules/catalog/domain/rules.py`.
 *
 * Like the pricing mirror, this half is a UX affordance: it lets the configurator explain a
 * conflict the moment it appears instead of after a round trip. The Python half decides
 * whether a quote is accepted. Both are held to `fixtures/pricing-cases.json`.
 */

export type RuleRelation = "requires" | "excludes";

export type OptionRule = {
  subject: string;
  relation: RuleRelation;
  object: string;
};

export type RuleablePlatform = {
  slug: string;
  rules: OptionRule[];
};

export type RuleViolation = {
  kind: RuleRelation;
  option: string;
  needs: string | null;
  conflicts_with: string | null;
};

/**
 * Return every rule violated by the selection.
 *
 * A `requires` rule fires when its subject is selected without its object. An `excludes` rule
 * fires when both its subject and object are selected -- which side the data calls "subject"
 * does not matter, since the check is symmetric on selection membership.
 */
export function validateSelection(
  platform: RuleablePlatform,
  selectedOptionSlugs: string[],
): RuleViolation[] {
  const selected = new Set(selectedOptionSlugs);
  const violations: RuleViolation[] = [];

  for (const rule of platform.rules) {
    if (!selected.has(rule.subject)) continue;

    if (rule.relation === "requires" && !selected.has(rule.object)) {
      violations.push({
        kind: "requires",
        option: rule.subject,
        needs: rule.object,
        conflicts_with: null,
      });
    } else if (rule.relation === "excludes" && selected.has(rule.object)) {
      violations.push({
        kind: "excludes",
        option: rule.subject,
        needs: null,
        conflicts_with: rule.object,
      });
    }
  }

  return violations;
}

/**
 * The violations that would appear if `slug` were added to the current selection, so an option
 * can say *why* it is unavailable before it is clicked rather than only after.
 */
export function violationsIfSelected(
  platform: RuleablePlatform,
  selectedOptionSlugs: string[],
  slug: string,
): RuleViolation[] {
  if (selectedOptionSlugs.includes(slug)) return [];
  const after = validateSelection(platform, [...selectedOptionSlugs, slug]);
  const before = new Set(validateSelection(platform, selectedOptionSlugs).map(violationKey));
  return after.filter((violation) => !before.has(violationKey(violation)));
}

export function violationKey(violation: RuleViolation): string {
  return `${violation.kind}:${violation.option}:${violation.needs ?? violation.conflicts_with}`;
}
