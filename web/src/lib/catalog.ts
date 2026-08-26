import { cacheLife, cacheTag } from "next/cache";

import { fetchCatalog, fetchPlatform, type Catalog, type Platform } from "@/lib/api";

/**
 * The only place page components should reach for catalog data. Reads are wrapped in `use
 * cache` so a slow or down API costs nothing per request; FastAPI busts these tags over the
 * revalidation webhook when catalog rows change (see docs/decisions.md).
 */

export async function getCatalog(): Promise<Catalog> {
  "use cache";
  cacheLife("hours");
  cacheTag("catalog");

  return fetchCatalog();
}

export async function getPlatform(slug: string): Promise<Platform | null> {
  "use cache";
  cacheLife("hours");
  cacheTag(`platform-${slug}`);

  return fetchPlatform(slug);
}
