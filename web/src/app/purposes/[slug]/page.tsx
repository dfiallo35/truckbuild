import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";

import { CTAButton } from "@/components/CTAButton";
import { PriceTag } from "@/components/PriceTag";
import { SectionHeading } from "@/components/SectionHeading";
import { getPlatform } from "@/lib/catalog";
import { getPurpose, PURPOSES } from "@/lib/purposes";

export function generateStaticParams() {
  return PURPOSES.map((purpose) => ({ slug: purpose.slug }));
}

export async function generateMetadata(props: PageProps<"/purposes/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const purpose = getPurpose(slug);
  if (!purpose) return {};

  return {
    title: purpose.name,
    description: purpose.description,
    alternates: { canonical: `/purposes/${purpose.slug}` },
    openGraph: {
      title: `${purpose.name} — ${purpose.tagline}`,
      description: purpose.description,
      images: [{ url: purpose.heroImage.url, alt: purpose.heroImage.altText }],
    },
  };
}

export default async function PurposePage(props: PageProps<"/purposes/[slug]">) {
  const { slug } = await props.params;
  const purpose = getPurpose(slug);
  if (!purpose) notFound();

  const platform = await getPlatform(purpose.platformSlug);

  return (
    <>
      <section className="relative flex min-h-[70vh] flex-col justify-end overflow-hidden">
        <Image
          src={purpose.heroImage.url}
          alt={purpose.heroImage.altText}
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        <div className="from-canvas via-canvas/40 absolute inset-0 bg-gradient-to-t to-transparent" />
        <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 pt-40 pb-16 md:px-10">
          <span className="font-data text-accent text-xs tracking-[0.18em] uppercase">
            {purpose.tagline}
          </span>
          <h1 className="font-display text-ink text-4xl tracking-tight uppercase md:text-6xl">
            {purpose.name}
          </h1>
          <p className="text-ink-muted max-w-2xl text-base md:text-lg">{purpose.description}</p>
        </div>
      </section>

      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-2">
          <div className="flex flex-col gap-6">
            <SectionHeading eyebrow="The brief" title="What this mission needs" />
            <ul className="text-ink-muted flex flex-col gap-2 text-sm">
              {purpose.briefPoints.map((point) => (
                <li key={point} className="flex gap-3">
                  <span className="text-accent">—</span>
                  {point}
                </li>
              ))}
            </ul>
          </div>

          {platform ? (
            <div className="flex flex-col gap-6">
              <SectionHeading eyebrow="The platform" title={platform.name} />
              <p className="text-ink-muted text-sm">{platform.chassis_basis}</p>
              <PriceTag cents={platform.base_price_cents} size="sm" />
              <CTAButton href={`/builds/${platform.slug}`} className="self-start">
                View the {platform.name} build
              </CTAButton>
            </div>
          ) : null}
        </div>
      </section>

      <section className="py-section px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-8">
          <SectionHeading title="Not sure this is the right fit?" />
          <CTAButton href="/contact" variant="secondary">
            Talk to sales
          </CTAButton>
        </div>
      </section>
    </>
  );
}
