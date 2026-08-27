import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";

import { CTAButton } from "@/components/CTAButton";
import { JsonLd } from "@/components/JsonLd";
import { MediaBlock } from "@/components/MediaBlock";
import { PriceTag } from "@/components/PriceTag";
import { SectionHeading } from "@/components/SectionHeading";
import { SpecList } from "@/components/SpecList";
import { getCatalog, getPlatform } from "@/lib/catalog";
import { SITE_NAME, SITE_URL } from "@/lib/site";

export async function generateStaticParams() {
  const catalog = await getCatalog();
  return catalog.platforms.map((platform) => ({ slug: platform.slug }));
}

export async function generateMetadata(props: PageProps<"/builds/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) return {};

  const title = platform.name;
  const description = `${platform.name} — ${platform.purpose}. Built on a ${platform.chassis_basis}, starting at $${(platform.base_price_cents / 100).toLocaleString("en-US")}.`;

  return {
    title,
    description,
    alternates: { canonical: `/builds/${platform.slug}` },
    openGraph: {
      title,
      description,
      url: `${SITE_URL}/builds/${platform.slug}`,
      images: platform.hero_image
        ? [{ url: platform.hero_image.url, alt: platform.hero_image.alt_text }]
        : undefined,
    },
  };
}

export default async function PlatformPage(props: PageProps<"/builds/[slug]">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) notFound();

  const priceFormatted = (platform.base_price_cents / 100).toLocaleString("en-US");

  const productJsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: platform.name,
    description: platform.purpose,
    image: platform.hero_image ? [`${SITE_URL}${platform.hero_image.url}`] : undefined,
    brand: { "@type": "Organization", name: SITE_NAME },
    offers: {
      "@type": "Offer",
      priceCurrency: "USD",
      price: (platform.base_price_cents / 100).toFixed(2),
      availability: "https://schema.org/InStock",
      url: `${SITE_URL}/builds/${platform.slug}`,
    },
  };

  return (
    <>
      <JsonLd data={productJsonLd} />

      <section className="relative flex min-h-[70vh] flex-col justify-end overflow-hidden">
        {platform.hero_image ? (
          <>
            <Image
              src={platform.hero_image.url}
              alt={platform.hero_image.alt_text}
              fill
              priority
              sizes="100vw"
              className="object-cover"
            />
            <div className="from-canvas via-canvas/40 absolute inset-0 bg-gradient-to-t to-transparent" />
          </>
        ) : null}
        <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 pt-40 pb-16 md:px-10">
          <span className="font-data text-ink-faint text-xs tracking-[0.18em] uppercase">
            {platform.chassis_basis}
          </span>
          <h1 className="font-display text-ink text-4xl tracking-tight uppercase md:text-6xl">
            {platform.name}
          </h1>
          <p className="text-ink-muted max-w-2xl text-base md:text-lg">{platform.purpose}</p>
          <div className="mt-4 flex flex-wrap items-end gap-8">
            <PriceTag cents={platform.base_price_cents} />
            <CTAButton href={`/configurator/${platform.slug}`}>Start customizing</CTAButton>
          </div>
        </div>
      </section>

      {platform.gallery.length > 0 ? (
        <section className="border-border border-b px-6 py-16 md:px-10">
          <div className="mx-auto grid max-w-6xl gap-6 sm:grid-cols-2">
            {platform.gallery.map((asset) => (
              <MediaBlock
                key={asset.url}
                src={asset.url}
                alt={asset.alt_text}
                sizes="(min-width: 640px) 50vw, 100vw"
              />
            ))}
          </div>
        </section>
      ) : null}

      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-2">
          <div className="flex flex-col gap-6">
            <SectionHeading eyebrow="Overview" title="Specification" />
            <SpecList
              specs={[
                { label: "Chassis basis", value: platform.chassis_basis },
                { label: "Purpose", value: platform.purpose },
                { label: "Starting at", value: `$${priceFormatted}` },
              ]}
            />
          </div>
          <div className="flex flex-col gap-6">
            <SectionHeading eyebrow="Included" title="Standard equipment" />
            <ul className="text-ink-muted flex flex-col gap-2 text-sm">
              {platform.standard_equipment.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="text-accent">—</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {platform.spec_highlights.length > 0 ? (
        <section className="border-border border-b px-6 py-16 md:px-10">
          <div className="mx-auto flex max-w-6xl flex-col gap-6">
            <SectionHeading eyebrow="Capability" title="Spec highlights" />
            <ul className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
              {platform.spec_highlights.map((item) => (
                <li
                  key={item}
                  className="border-border font-data text-ink-muted border px-4 py-3 text-sm"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <section className="py-section px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-8">
          <SectionHeading
            eyebrow="Configure"
            title="Chassis & options"
            description="Every option group below is configured step by step in the builder, with incompatible combinations flagged before you order."
          />
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {platform.option_groups.map((group) => (
              <div key={group.slug} className="flex flex-col gap-3">
                <h3 className="font-display text-ink text-lg tracking-tight uppercase">
                  {group.name}
                </h3>
                <ul className="divide-border font-data divide-y text-sm">
                  {group.options.map((option) => (
                    <li
                      key={option.slug}
                      className="text-ink-muted flex items-baseline justify-between gap-4 py-2"
                    >
                      <span>{option.name}</span>
                      <span className="text-ink-faint tabular-nums">
                        {option.price_delta_cents === 0
                          ? "Included"
                          : `+$${(option.price_delta_cents / 100).toLocaleString("en-US")}`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <CTAButton href={`/configurator/${platform.slug}`} className="self-start">
            Start customizing
          </CTAButton>
        </div>
      </section>
    </>
  );
}
