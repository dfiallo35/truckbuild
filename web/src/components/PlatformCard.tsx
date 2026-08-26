import Link from "next/link";

import { MediaBlock } from "@/components/MediaBlock";
import { PriceTag } from "@/components/PriceTag";
import type { Platform } from "@/lib/api";

type PlatformCardProps = {
  platform: Pick<
    Platform,
    "slug" | "name" | "purpose" | "chassis_basis" | "base_price_cents" | "hero_image"
  >;
};

export function PlatformCard({ platform }: PlatformCardProps) {
  return (
    <Link
      href={`/platforms/${platform.slug}`}
      className="group focus-visible:outline-accent flex flex-col gap-4 focus-visible:outline-2 focus-visible:outline-offset-4"
    >
      {platform.hero_image ? (
        <MediaBlock
          src={platform.hero_image.url}
          alt={platform.hero_image.alt_text}
          aspect="video"
          className="transition-[filter] duration-300 group-hover:brightness-110"
        />
      ) : null}
      <div className="flex flex-col gap-2">
        <span className="font-data text-ink-faint text-xs tracking-[0.18em] uppercase">
          {platform.chassis_basis}
        </span>
        <h3 className="font-display text-ink group-hover:text-accent text-2xl tracking-tight uppercase">
          {platform.name}
        </h3>
        <p className="text-ink-muted text-sm">{platform.purpose}</p>
        <PriceTag cents={platform.base_price_cents} size="sm" className="mt-1" />
      </div>
    </Link>
  );
}
