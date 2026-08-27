import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ConfiguratorBar } from "@/components/configurator/ConfiguratorBar";
import { ConfiguratorShell } from "@/components/configurator/ConfiguratorShell";
import { getCatalog, getPlatform } from "@/lib/catalog";
import { SITE_URL } from "@/lib/site";

export async function generateStaticParams() {
  const catalog = await getCatalog();
  return catalog.platforms.map((platform) => ({ slug: platform.slug }));
}

export async function generateMetadata(props: PageProps<"/configurator/[slug]">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) return {};

  const title = `Configure the ${platform.name}`;
  const description = `Build a ${platform.name} on a ${platform.chassis_basis} — pick your options and watch the price as you go.`;

  return {
    title,
    description,
    alternates: { canonical: `/configurator/${platform.slug}` },
    // Every build is a query string away from every other one; the platform page is the
    // canonical thing to index, not one of a combinatorial number of configured URLs.
    robots: { index: false, follow: true },
    openGraph: { title, description, url: `${SITE_URL}/configurator/${platform.slug}` },
  } satisfies Metadata;
}

export default async function ConfiguratorPage(props: PageProps<"/configurator/[slug]">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) notFound();

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <ConfiguratorBar platform={platform} />
      {/* The build lives in the query string, so the shell reads searchParams and is dynamic.
          The bar above it prerenders; this streams in. See docs/decisions.md on caching. */}
      <Suspense fallback={<ShellFallback />}>
        <ConfiguratorShell platform={platform} />
      </Suspense>
    </div>
  );
}

function ShellFallback() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <p className="font-data text-ink-faint animate-pulse text-xs tracking-[0.2em] uppercase">
        Loading build
      </p>
    </div>
  );
}
