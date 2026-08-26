import type { MetadataRoute } from "next";

import { getCatalog } from "@/lib/catalog";
import { PURPOSES } from "@/lib/purposes";
import { SITE_URL } from "@/lib/site";

const STATIC_ROUTES = [
  "",
  "/builds",
  "/process",
  "/gallery",
  "/about",
  "/contact",
  "/legal/privacy",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const catalog = await getCatalog();

  const staticEntries: MetadataRoute.Sitemap = STATIC_ROUTES.map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.7,
  }));

  const platformEntries: MetadataRoute.Sitemap = catalog.platforms.map((platform) => ({
    url: `${SITE_URL}/builds/${platform.slug}`,
    changeFrequency: "weekly",
    priority: 0.9,
  }));

  const purposeEntries: MetadataRoute.Sitemap = PURPOSES.map((purpose) => ({
    url: `${SITE_URL}/purposes/${purpose.slug}`,
    changeFrequency: "monthly",
    priority: 0.8,
  }));

  return [...staticEntries, ...platformEntries, ...purposeEntries];
}
