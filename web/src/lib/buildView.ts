import { useMemo } from "react";

import { BUILD_PARAM, decodeSelection, toPriceable, toRuleable } from "@/lib/build";
import type { Platform } from "@/lib/contract";
import { priceBuild, type PriceBreakdown } from "@/lib/pricing";
import { validateSelection, type RuleViolation } from "@/lib/rules";

/**
 * The build a platform's search params encode, priced and checked against its rules -- the one
 * derivation `ConfiguratorShell` and `BuildRequest` each ran as a pair of separate `useMemo`s
 * before stage 13.
 */
export type BuildView = {
  selected: string[];
  breakdown: PriceBreakdown;
  violations: RuleViolation[];
};

export function selectionFromParams(
  platform: Platform,
  searchParams: Pick<URLSearchParams, "get">,
): string[] {
  return decodeSelection(platform, searchParams.get(BUILD_PARAM));
}

export function deriveBuildView(
  platform: Platform,
  selected: string[],
): Omit<BuildView, "selected"> {
  return {
    breakdown: priceBuild(toPriceable(platform), selected),
    violations: validateSelection(toRuleable(platform), selected),
  };
}

export function useBuildView(
  platform: Platform,
  searchParams: Pick<URLSearchParams, "get">,
): BuildView {
  const selected = useMemo(
    () => selectionFromParams(platform, searchParams),
    [platform, searchParams],
  );
  const { breakdown, violations } = useMemo(
    () => deriveBuildView(platform, selected),
    [platform, selected],
  );
  return { selected, breakdown, violations };
}
