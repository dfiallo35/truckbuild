/**
 * What the build view's loading readout should say, derived from `GLTFLoader`'s progress events.
 *
 * Pure on purpose. `docs/testing.md` puts Vitest on logic with no DOM behind it, and the
 * interesting part of a loading state is exactly this: which phase we are in and whether the
 * transfer can be measured at all. `BuildViewerLoading` renders the result; nothing else
 * decides it.
 */
export type LoadProgress = { loaded: number; total: number };

export type LoadReadout = {
  label: string;
  /** `null` whenever the transfer cannot be measured -- render the indeterminate sweep. */
  percent: number | null;
};

/**
 * `null` means the lazily imported viewer chunk is still on the wire, so no byte counts exist
 * yet -- three.js has not been asked for the GLB because three.js is not here.
 *
 * The indeterminate sweep is what visitors actually see today, and both reasons for it are
 * measured rather than assumed:
 *
 * - **No length at all.** `total` is 0 whenever the response carried no `Content-Length`.
 *   Vercel Blob serves the production GLB as `content-encoding: br` with no length, and Next's
 *   own `public/` handler serves it gzip-encoded and chunked, so neither deployment offers one.
 *   This is the normal path, not a defensive branch.
 * - **A length that measures something else.** `Content-Length` counts bytes on the wire, while
 *   `FileLoader` counts them after the browser has decompressed them. Pair the two and the bar
 *   sprints to 100% at a third of the real transfer and then sits there lying. So a `loaded`
 *   past `total` is taken as proof the length was never comparable, and the bar goes back to
 *   admitting it does not know -- rather than clamping, which would keep the lie and cap it.
 *
 * The percentage therefore appears only where the length is real: an uncompressed GLB, which is
 * what an already-Draco-compressed model gets served as.
 */
export function readoutFor(progress: LoadProgress | null): LoadReadout {
  if (!progress) return { label: "Preparing viewer", percent: null };
  const { loaded, total } = progress;
  if (total <= 0 || loaded > total) return { label: "Loading 3D model", percent: null };
  return { label: "Loading 3D model", percent: Math.max(Math.round((loaded / total) * 100), 0) };
}

/**
 * Whether two progress events would put the same thing on screen. `onProgress` fires once per
 * network chunk -- hundreds of times for a multi-megabyte GLB -- and re-rendering the
 * configurator that often would jank the very load being reported. Bailing out on an unchanged
 * readout caps it at roughly one render per percentage point.
 */
export function readoutsMatch(a: LoadProgress | null, b: LoadProgress | null): boolean {
  const left = readoutFor(a);
  const right = readoutFor(b);
  return left.label === right.label && left.percent === right.percent;
}
