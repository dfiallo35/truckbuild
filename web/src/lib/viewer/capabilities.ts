/**
 * Split out of `scene.ts` deliberately: this is imported by `BuildViewer.tsx`, which is *not*
 * lazy, to decide whether to mount the lazy 3D chunk at all. `scene.ts` imports `three`, the
 * GLTF loader and orbit controls at module scope -- if this check lived there too, importing it
 * would pull that whole graph into the eager bundle regardless of which branch actually runs,
 * defeating the lazy split `next/dynamic` is there to create.
 */
export function isWebglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}
