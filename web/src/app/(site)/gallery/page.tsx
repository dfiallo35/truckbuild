import type { Metadata } from "next";

import { MediaBlock } from "@/components/MediaBlock";
import { SectionHeading } from "@/components/SectionHeading";
import { getCatalog } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Gallery",
  description: "Every TruckBuild platform, in the field.",
};

export default async function GalleryPage() {
  const catalog = await getCatalog();
  const shots = catalog.platforms.flatMap((platform) => {
    const assets = platform.hero_image
      ? [platform.hero_image, ...platform.gallery]
      : platform.gallery;
    return assets.map((asset) => ({ ...asset, caption: platform.name }));
  });

  return (
    <section className="py-section px-6 md:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-12">
        <SectionHeading
          eyebrow="In the field"
          title="Gallery"
          description="Every platform, working the job it was built for."
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {shots.map((shot, index) => (
            <MediaBlock
              key={shot.url}
              src={shot.url}
              alt={shot.alt_text}
              caption={shot.caption}
              priority={index === 0}
              sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
            />
          ))}
        </div>
      </div>
    </section>
  );
}
