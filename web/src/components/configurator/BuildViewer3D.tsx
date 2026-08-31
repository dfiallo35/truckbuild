"use client";

import { useEffect, useMemo, useRef } from "react";

import { allOptions } from "@/lib/build";
import type { Platform } from "@/lib/contract";
import {
  createScene,
  type ViewerEffect,
  type ViewerHandle,
  type ViewerModel,
} from "@/lib/viewer/scene";

/**
 * The canvas half of the build view -- dynamically imported by `BuildViewer` with `ssr: false`,
 * since a real WebGL context does not exist on the server and three.js is 130-160 KiB gzipped
 * on its own (see `docs/stages/16-3d-viewer.md`). `BuildViewer` renders this only once
 * `platform.model` is non-null, so `model` here is never null.
 *
 * React owns `selected`; `scene.ts` owns the WebGL. One effect creates and tears down the
 * scene, a second calls `applySelection` whenever the build changes, and a `ResizeObserver`
 * keeps the drawing buffer matched to the box the flex layout gives the canvas.
 *
 * Default export deliberately: `next/dynamic(() => import("./BuildViewer3D"))` without a
 * `.then()` unwrapping a named export is what the bundler reliably treats as a real
 * code-split boundary -- with a named export it silently pulled three.js into the
 * configurator route's first load instead of the lazy chunk it was supposed to be.
 */
export default function BuildViewer3D({
  platform,
  selected,
  onFirstFrame,
  onProgress,
  onError,
}: {
  platform: Platform;
  selected: string[];
  onFirstFrame: () => void;
  onProgress: (loaded: number, total: number) => void;
  onError: (error: unknown) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<ViewerHandle | null>(null);

  const model: ViewerModel | null = useMemo(() => {
    if (!platform.model) return null;
    const effects: Record<string, ViewerEffect> = {};
    for (const option of allOptions(platform)) {
      if (!option.model_effect) continue;
      effects[option.slug] = {
        nodes: option.model_effect.nodes,
        materialTarget: option.model_effect.material_target,
        baseColorHex: option.model_effect.base_color_hex,
        metalness: option.model_effect.metalness,
        roughness: option.model_effect.roughness,
      };
    }
    return {
      url: platform.model.url,
      cameraOrbitDeg: platform.model.camera_orbit_deg,
      cameraDistanceM: platform.model.camera_distance_m,
      cameraTargetYM: platform.model.camera_target_y_m,
      effects,
    };
  }, [platform]);

  // The callbacks are passed fresh every render from BuildViewer; only `model` should ever
  // re-create the scene, so the latest ones are read through a ref rather than joining the
  // effect's dependency array.
  const callbacksRef = useRef({ onFirstFrame, onProgress, onError });
  useEffect(() => {
    callbacksRef.current = { onFirstFrame, onProgress, onError };
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !model) return;

    let cancelled = false;
    createScene(canvas, model, {
      onFirstFrame: () => callbacksRef.current.onFirstFrame(),
      onProgress: (loaded, total) => callbacksRef.current.onProgress(loaded, total),
      onError: (error) => callbacksRef.current.onError(error),
    })
      .then((handle) => {
        if (cancelled) {
          handle.dispose();
          return;
        }
        handleRef.current = handle;
        handle.applySelection(selected);
      })
      .catch((error) => callbacksRef.current.onError(error));

    return () => {
      cancelled = true;
      handleRef.current?.dispose();
      handleRef.current = null;
    };
    // `selected` deliberately excluded: the mount effect applies the initial selection itself,
    // and every later change is handled by the effect below without tearing the scene down.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model]);

  useEffect(() => {
    handleRef.current?.applySelection(selected);
  }, [selected]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() => handleRef.current?.resize());
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  return (
    <canvas
      ref={canvasRef}
      tabIndex={0}
      className="focus-visible:outline-accent absolute inset-0 h-full w-full touch-none -outline-offset-4 focus-visible:outline-2"
    />
  );
}
