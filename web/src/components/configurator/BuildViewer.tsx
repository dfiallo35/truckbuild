"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { Platform } from "@/lib/contract";
import { allOptions } from "@/lib/build";
import { isWebglAvailable } from "@/lib/viewer/capabilities";
import { readoutsMatch, type LoadProgress } from "@/lib/viewer/progress";
import { BuildViewerLoading } from "./BuildViewerLoading";

const BuildViewer3D = dynamic(() => import("./BuildViewer3D"), { ssr: false });

/**
 * A thin shell around the real work in `BuildViewer3D`. `BuildViewer3D` is a lazily loaded
 * chunk (three.js is 130-160 KiB gzipped on its own) mounted only once this shell knows there
 * is a model to show and a context to render it in, so a platform mid-photoshoot with no synced
 * model costs nothing beyond the poster it would have shown anyway.
 *
 * `platform.hero_image` is that poster, and it is shown in exactly two situations: a platform
 * with no model at all, and a browser that turned out not to be able to render one -- the
 * "no-WebGL position" in `docs/stages/16-3d-viewer.md`. It is deliberately *not* shown while the
 * model loads. The stretch between "there is a model" and "the first frame rendered" covers two
 * downloads, the three.js chunk and then the GLB, and holding a photograph across it promises a
 * finished picture that is about to be replaced by a different one. `BuildViewerLoading`
 * narrates that stretch instead, over the empty frame the build is about to occupy, and gives
 * way the moment the canvas paints.
 *
 * Because the decision keys off `platform.model` rather than the stage, a platform with a model
 * never flashes its photograph on the first paint on the way to the viewer.
 *
 * `data-testid="build-viewer"` and the `role="img"` wrapper are load-bearing:
 * `e2e/configurator.spec.ts` and `e2e/a11y.spec.ts` both address the viewer by them.
 */
export function BuildViewer({ platform, selected }: { platform: Platform; selected: string[] }) {
  const [stage, setStage] = useState<"poster" | "loading" | "ready" | "unavailable">("poster");
  const [progress, setProgress] = useState<LoadProgress | null>(null);

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

  // `onProgress` fires once per network chunk. Keeping the previous object whenever the readout
  // would look the same turns hundreds of renders into roughly one per percentage point.
  const handleProgress = useCallback((loaded: number, total: number) => {
    setProgress((current) => {
      const next = { loaded, total };
      return readoutsMatch(current, next) ? current : next;
    });
  }, []);

  const mount3D = stage === "loading" || stage === "ready";
  const showPoster = !platform.model || stage === "unavailable";

  return (
    <div
      data-testid="build-viewer"
      className="relative flex min-h-0 items-center justify-center overflow-hidden px-4 py-6 md:p-0"
    >
      {/* Two shapes, one element. Where the page scrolls -- a phone -- the frame has to carry its
          own height, so it is a 16:9 box in the flow. Where the layout is a fixed-height grid it
          fills its cell edge to edge instead: a smaller box inside a larger pane is an invisible
          window until someone zooms the model into its edges and finds it, which is exactly the
          crop this used to produce. `scene.ts` reframes to whatever aspect the cell turns out to
          be, so filling a tall, narrow column does not cost the build its bumpers. */}
      <div
        role="img"
        aria-label={description}
        className="relative aspect-[16/9] w-full max-w-4xl self-center md:aspect-auto md:h-full md:max-w-none"
      >
        {platform.hero_image ? (
          <Image
            src={platform.hero_image.url}
            alt=""
            fill
            // Preloaded only where it is the picture of record. On a platform with a model the
            // photo is a fallback that will probably never be shown, and racing it against the
            // GLB would slow down the thing the visitor is actually waiting for.
            priority={showPoster}
            sizes="(min-width: 768px) 60vw, 100vw"
            className={`object-contain transition-opacity duration-500 ease-out motion-reduce:transition-none ${
              showPoster ? "opacity-100" : "opacity-0"
            }`}
          />
        ) : null}

        {mount3D ? (
          <BuildViewer3D
            platform={platform}
            selected={selected}
            onFirstFrame={() => setStage("ready")}
            onProgress={handleProgress}
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

      {stage === "loading" ? <BuildViewerLoading progress={progress} /> : null}

      <p className="font-data text-ink-faint absolute bottom-3 left-1/2 hidden -translate-x-1/2 text-[0.625rem] tracking-[0.2em] whitespace-nowrap uppercase sm:block">
        Illustrative render — final build may vary
      </p>
    </div>
  );
}
