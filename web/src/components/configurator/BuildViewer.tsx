"use client";

import Image from "next/image";
import { useMemo } from "react";

import type { Platform } from "@/lib/api";
import { allOptions } from "@/lib/build";

/**
 * The build as a layered composite: the platform's base image with one image per selected
 * option stacked by z-index. It delivers most of the perceived value of a 3D viewer at a
 * fraction of the cost, and an option with nothing to show simply contributes no layer.
 *
 * Every layer stays mounted and cross-fades on opacity rather than mounting and unmounting,
 * so switching an option is instant instead of a fetch away.
 */
export function BuildViewer({ platform, selected }: { platform: Platform; selected: string[] }) {
  const chosen = useMemo(() => new Set(selected), [selected]);

  const layers = useMemo(
    () =>
      allOptions(platform)
        .flatMap((option) => (option.layer ? [{ slug: option.slug, layer: option.layer }] : []))
        .sort((a, b) => a.layer.z_index - b.layer.z_index),
    [platform],
  );

  const description = useMemo(() => {
    const names = allOptions(platform)
      .filter((option) => chosen.has(option.slug))
      .map((option) => option.name);
    return `${platform.name}, configured with ${names.join(", ")}.`;
  }, [chosen, platform]);

  return (
    <div className="relative flex min-h-0 items-center justify-center overflow-hidden px-4 py-6 md:px-8">
      <div
        role="img"
        aria-label={description}
        className="relative aspect-[16/9] w-full max-w-4xl self-center"
      >
        {platform.viewer_base ? (
          <Image
            src={platform.viewer_base.url}
            alt=""
            fill
            priority
            sizes="(min-width: 768px) 60vw, 100vw"
            className="object-contain"
          />
        ) : null}

        {layers.map(({ slug, layer }) => (
          <Image
            key={slug}
            src={layer.url}
            alt=""
            fill
            sizes="(min-width: 768px) 60vw, 100vw"
            style={{ zIndex: layer.z_index, opacity: chosen.has(slug) ? 1 : 0 }}
            className="object-contain transition-opacity duration-300 ease-out motion-reduce:transition-none"
          />
        ))}
      </div>

      <p className="font-data text-ink-faint absolute bottom-3 left-1/2 hidden -translate-x-1/2 text-[0.625rem] tracking-[0.2em] whitespace-nowrap uppercase sm:block">
        Illustrative render — final build may vary
      </p>
    </div>
  );
}
