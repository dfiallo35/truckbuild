import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ConfiguratorBar } from "@/components/configurator/ConfiguratorBar";
import { BuildRequest } from "@/components/leads/BuildRequest";
import { getCatalog, getPlatform } from "@/lib/catalog";

export async function generateStaticParams() {
  const catalog = await getCatalog();
  return catalog.platforms.map((platform) => ({ slug: platform.slug }));
}

export async function generateMetadata(props: PageProps<"/configurator/[slug]/request">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) return {};

  return {
    title: `Request a ${platform.name}`,
    description: `Send your ${platform.name} build to a TruckBuild specialist for a proper quote.`,
    // A form carrying somebody's half-finished build is not a landing page.
    robots: { index: false, follow: true },
  } satisfies Metadata;
}

export default async function RequestPage(props: PageProps<"/configurator/[slug]/request">) {
  const { slug } = await props.params;
  const platform = await getPlatform(slug);
  if (!platform) notFound();

  return (
    <div className="flex min-h-dvh flex-col">
      <ConfiguratorBar platform={platform} />
      {/* The build is in the query string, so this half is dynamic while the bar above it
          prerenders -- the same split the configurator uses. See docs/decisions.md. */}
      <Suspense fallback={<RequestFallback />}>
        <BuildRequest platform={platform} />
      </Suspense>
    </div>
  );
}

function RequestFallback() {
  return (
    <div className="flex flex-1 items-center justify-center py-24">
      <p className="font-data text-ink-faint animate-pulse text-xs tracking-[0.2em] uppercase">
        Loading build
      </p>
    </div>
  );
}
