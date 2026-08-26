export type Purpose = {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  /** The platform this vertical currently routes to. One purpose, one platform, for now --
   *  the model allows more later without a page rewrite. */
  platformSlug: string;
  heroImage: { url: string; altText: string };
  briefPoints: ReadonlyArray<string>;
};

/**
 * Purpose verticals are editorial framing over the catalog, not a backend entity -- the
 * platform a purpose routes to is looked up from FastAPI at request time via `platformSlug`.
 * Renaming a `slug` here is a breaking change the same as a platform slug (see
 * docs/domain-model.md).
 */
export const PURPOSES: ReadonlyArray<Purpose> = [
  {
    slug: "expedition",
    name: "Expedition",
    tagline: "Overland habitat for weeks off the grid",
    description:
      "Multi-week range, self-contained water and power, and a shell that shrugs off washboard roads. Built for crews who measure a trip in fuel stops, not nights.",
    platformSlug: "bristlecone",
    heroImage: {
      url: "/images/bristlecone/hero.jpg",
      altText: "Bristlecone expedition platform against a dusk horizon",
    },
    briefPoints: [
      "800+ mile range between fuel stops",
      "Insulated habitat shell, standing headroom optional",
      "Fresh water, galley, and sleeping quarters built in",
    ],
  },
  {
    slug: "service",
    name: "Service",
    tagline: "A mobile shop that shows up ready to work",
    description:
      "Everything a fabrication or maintenance crew needs bolted down and organized: power tools, compressed air, and storage that doesn't shift on the job site.",
    platformSlug: "ironwood",
    heroImage: {
      url: "/images/ironwood/hero.jpg",
      altText: "Ironwood service platform on a job site at golden hour",
    },
    briefPoints: [
      "Onboard power for shop tools anywhere on site",
      "Modular storage rated for daily loading",
      "Crew cab standard for a full field team",
    ],
  },
  {
    slug: "response",
    name: "Response",
    tagline: "Command and access when minutes matter",
    description:
      "A platform built around visibility, communications, and getting through terrain a stock truck can't. Configured for crews who are first on scene, not last.",
    platformSlug: "sentinel",
    heroImage: {
      url: "/images/sentinel/hero.jpg",
      altText: "Sentinel response platform staged at dusk with lightbar active",
    },
    briefPoints: [
      "Elevated lighting and comms mounting standard",
      "Reinforced chassis for off-road access",
      "Command interior configurable to the mission",
    ],
  },
];

export function getPurpose(slug: string): Purpose | undefined {
  return PURPOSES.find((purpose) => purpose.slug === slug);
}

export function getPurposeForPlatform(platformSlug: string): Purpose | undefined {
  return PURPOSES.find((purpose) => purpose.platformSlug === platformSlug);
}
