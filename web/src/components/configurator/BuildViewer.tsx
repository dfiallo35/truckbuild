"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";

import type { Platform } from "@/lib/contract";
import { allOptions } from "@/lib/build";
import { isWebglAvailable } from "@/lib/viewer/capabilities";

const BuildViewer3D = dynamic(() => import("./BuildViewer3D"), { ssr: false });

/**
 * A thin shell around the real work in `BuildViewer3D`: `platform.hero_image` is the poster,
 * shown immediately and while the GLB streams in, and stays the terminal state on a device with
 * no WebGL or a model that failed to load -- see the "no-WebGL position" in
 * `docs/stages/16-3d-viewer.md`. `BuildViewer3D` is a lazily loaded chunk (three.js is 130-160
 * KiB gzipped on its own) mounted only once this shell knows there is a model to show and a
 * context to render it in, so a platform mid-photoshoot with no synced model costs nothing
 * beyond the poster it would have shown anyway.
 *
 * `data-testid="build-viewer"` and the `role="img"` wrapper are load-bearing:
 * `e2e/configurator.spec.ts` and `e2e/a11y.spec.ts` both address the viewer by them.
 */
export function BuildViewer({ platform, selected }: { platform: Platform; selected: string[] }) {
  const [stage, setStage] = useState<"poster" | "loading" | "ready" | "unavailable">("poster");

  // Deciding whether WebGL exists and mounting the 3D chunk are both client-only, so the first
  // render -- server and client alike -- is always the poster. That is what keeps this an
  // upgrade rather than a hydration mismatch.
  useEffect(() => {
    const checkWebgl = () => {
      if (!platform.model) return;
      setStage(isWebglAvailable() ? "loading" : "unavailable");
    };
    checkWebgl();
  }, [platform.model]);

  const description = useMemo(() => {
    const chosen = new Set(selected);
    const names = allOptions(platform)
      .filter((option) => chosen.has(option.slug))
      .map((option) => option.name);
    return `${platform.name}, configured with ${names.join(", ")}.`;
  }, [selected, platform]);

  const mount3D = stage === "loading" || stage === "ready";

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
        {platform.hero_image ? (
          <Image
            src={platform.hero_image.url}
            alt=""
            fill
            priority
            sizes="(min-width: 768px) 60vw, 100vw"
            className={`object-contain transition-opacity duration-500 ease-out motion-reduce:transition-none ${
              stage === "ready" ? "opacity-0" : "opacity-100"
            }`}
          />
        ) : null}

        {mount3D ? (
          <BuildViewer3D
            platform={platform}
            selected={selected}
            onFirstFrame={() => setStage("ready")}
            onError={() => setStage("unavailable")}
          />
        ) : null}

        {stage === "unavailable" ? (
          <p className="font-body text-ink-muted absolute inset-x-4 bottom-10 text-center text-xs sm:bottom-12">
            3D preview isn&apos;t available in this browser — the photo above shows the{" "}
            {platform.name} in its standard configuration.
          </p>
        ) : null}
      </div>

      <p className="font-data text-ink-faint absolute bottom-3 left-1/2 hidden -translate-x-1/2 text-[0.625rem] tracking-[0.2em] whitespace-nowrap uppercase sm:block">
        Illustrative render — final build may vary
      </p>
    </div>
  );
}
