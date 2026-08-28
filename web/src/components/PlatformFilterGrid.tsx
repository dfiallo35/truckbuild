"use client";

import { useMemo, useState, type ReactNode } from "react";

import { PlatformCard } from "@/components/PlatformCard";
import type { Platform } from "@/lib/contract";

type FilterOption = {
  slug: string;
  label: string;
  platformSlug: string;
};

type PlatformFilterGridProps = {
  platforms: ReadonlyArray<
    Pick<
      Platform,
      "slug" | "name" | "purpose" | "chassis_basis" | "base_price_cents" | "hero_image"
    >
  >;
  filters: ReadonlyArray<FilterOption>;
};

const ALL_FILTER = "all";

/** Client-side only: the full catalog is small and already fetched server-side, so filtering by
 * purpose here needs no round trip. */
export function PlatformFilterGrid({ platforms, filters }: PlatformFilterGridProps) {
  const [active, setActive] = useState<string>(ALL_FILTER);

  const visible = useMemo(() => {
    if (active === ALL_FILTER) return platforms;
    const filter = filters.find((f) => f.slug === active);
    if (!filter) return platforms;
    return platforms.filter((platform) => platform.slug === filter.platformSlug);
  }, [active, filters, platforms]);

  return (
    <div className="flex flex-col gap-10">
      <div role="group" aria-label="Filter builds by purpose" className="flex flex-wrap gap-2">
        <FilterButton active={active === ALL_FILTER} onClick={() => setActive(ALL_FILTER)}>
          All
        </FilterButton>
        {filters.map((filter) => (
          <FilterButton
            key={filter.slug}
            active={active === filter.slug}
            onClick={() => setActive(filter.slug)}
          >
            {filter.label}
          </FilterButton>
        ))}
      </div>

      {visible.length > 0 ? (
        <div className="grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((platform) => (
            <PlatformCard key={platform.slug} platform={platform} />
          ))}
        </div>
      ) : (
        <p className="text-ink-muted text-sm">No builds match that filter yet.</p>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`font-data cursor-pointer border px-4 py-2 text-xs tracking-[0.14em] uppercase transition-colors ${
        active
          ? "border-accent bg-accent text-accent-ink"
          : "border-border-strong text-ink-muted hover:border-accent hover:text-accent"
      }`}
    >
      {children}
    </button>
  );
}
