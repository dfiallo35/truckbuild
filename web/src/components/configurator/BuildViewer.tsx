"use client";

import Image from "next/image";
import { useMemo } from "react";

import type { Platform } from "@/lib/contract";
import { allOptions } from "@/lib/build";

/**
 * The build as a layered composite: the platform's base image with one image per selected
 * option stacked by z-index. It delivers most of the perceived value of a 3D viewer at a
 * fraction of the cost, and an option with nothing to show simply contributes no layer.
 *
 * Every layer stays mounted and cross-fades on opacity rather than mounting and unmounting,
 * so switching an option is instant instead of a fetch away. That means the whole platform's
 * layer set downloads on load, which is the deliberate trade: the layers are small next to the
 * base render, and an option that visibly costs a network round trip stops feeling like a
 * configurator. What it does not survive is being ignored once the placeholder renders are
 * replaced by real photography -- hence the explicit priority below rather than an accident of
 * DOM order. The layers belonging to the step in front of the visitor are the ones needed
 * first; the rest may take their time.
 */
export function BuildViewer({
  platform,
  selected,
  activeGroupSlug,
}: {
  platform: Platform;
  selected: string[];
  /** Option group currently open in the panel; its layers load ahead of the others. */
  activeGroupSlug?: string;
}) {
  const chosen = useMemo(() => new Set(selected), [selected]);

  const layers = useMemo(
    () =>
      platform.option_groups
        .flatMap((group) =>
          group.options.flatMap((option) =>
            option.layer ? [{ slug: option.slug, layer: option.layer, groupSlug: group.slug }] : [],
          ),
        )
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
    <div
      data-testid="build-viewer"
      className="relative flex min-h-0 items-center justify-center overflow-hidden px-4 py-6 md:px-8"
    >
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

        {layers.map(({ slug, layer, groupSlug }) => (
          <Image
            key={slug}
            src={layer.url}
            alt=""
            fill
            sizes="(min-width: 768px) 60vw, 100vw"
            // Already-selected layers are on screen, and the open step's are one click from
            // being. Everything else is speculative, and should not compete with them.
            fetchPriority={chosen.has(slug) || groupSlug === activeGroupSlug ? "high" : "low"}
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
