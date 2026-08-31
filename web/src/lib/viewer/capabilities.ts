/**
 * Split out of `scene.ts` deliberately: this is imported by `BuildViewer.tsx`, which is *not*
 * lazy, to decide whether to mount the lazy 3D chunk at all. `scene.ts` imports `three`, the
 * GLTF loader and orbit controls at module scope -- if this check lived there too, importing it
 * would pull that whole graph into the eager bundle regardless of which branch actually runs,
 * defeating the lazy split `next/dynamic` is there to create.
 */

/**
 * Answered once per document. A browser caps how many WebGL contexts may be live at once
 * (sixteen in Chrome) and evicts the oldest to stay under it, so a probe that asks for a context
 * on every visit to the configurator and never gives one back eventually costs the viewer the
 * context it was probing on behalf of -- a leak that reports itself as "3D preview isn't
 * available", which is exactly the thing it was asked to measure. Whether the browser can do
 * WebGL at all does not change while the page is open, so asking twice was never useful.
 */
let supported: boolean | null = null;

export function isWebglAvailable(): boolean {
  if (supported !== null) return supported;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    // Handed straight back rather than left to garbage collection, which is not prompt enough
    // to keep a repeat visitor under the cap.
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    supported = gl !== null;
  } catch {
    supported = false;
  }
  return supported;
}
