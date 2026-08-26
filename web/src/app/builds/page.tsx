import type { Metadata } from "next";

import { PlatformFilterGrid } from "@/components/PlatformFilterGrid";
import { SectionHeading } from "@/components/SectionHeading";
import { getCatalog } from "@/lib/catalog";
import { PURPOSES } from "@/lib/purposes";

export const metadata: Metadata = {
  title: "Builds",
  description:
    "Browse every TruckBuild platform — expedition, service, and response upfits, each configured to order.",
};

export default async function BuildsPage() {
  const catalog = await getCatalog();
  const filters = PURPOSES.map((purpose) => ({
    slug: purpose.slug,
    label: purpose.name,
    platformSlug: purpose.platformSlug,
  }));

  return (
    <section className="py-section px-6 md:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-12">
        <SectionHeading
          eyebrow="The catalog"
          title="Builds"
          description="Every platform we build, each one engineered around a single mission. Filter by the job, or browse all three."
        />
        <PlatformFilterGrid platforms={catalog.platforms} filters={filters} />
      </div>
    </section>
  );
}
