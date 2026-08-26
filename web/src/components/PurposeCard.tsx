import Image from "next/image";
import Link from "next/link";

import type { Purpose } from "@/lib/purposes";

export function PurposeCard({ purpose }: { purpose: Purpose }) {
  return (
    <Link
      href={`/purposes/${purpose.slug}`}
      className="group focus-visible:outline-accent border-border relative flex aspect-[3/4] flex-col justify-end overflow-hidden border focus-visible:outline-2 focus-visible:outline-offset-4"
    >
      <Image
        src={purpose.heroImage.url}
        alt={purpose.heroImage.altText}
        fill
        sizes="(min-width: 640px) 33vw, 100vw"
        className="object-cover transition-[filter] duration-300 group-hover:brightness-110"
      />
      <div className="from-canvas via-canvas/50 absolute inset-0 bg-gradient-to-t to-transparent" />
      <div className="relative flex flex-col gap-2 p-6">
        <span className="font-data text-accent text-xs tracking-[0.18em] uppercase">
          {purpose.tagline}
        </span>
        <h3 className="font-display text-ink group-hover:text-accent text-2xl tracking-tight uppercase">
          {purpose.name}
        </h3>
      </div>
    </Link>
  );
}
