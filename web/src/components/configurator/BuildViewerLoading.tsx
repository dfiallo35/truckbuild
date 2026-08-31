"use client";

import { readoutFor, type LoadProgress } from "@/lib/viewer/progress";

/**
 * What occupies the build frame while it loads -- first the lazily imported three.js chunk, then
 * the GLB streaming in behind it.
 *
 * Deliberately an instrument rather than a spinner. `GLTFLoader` reports real bytes, so the
 * frame reports real bytes, in the same mono-uppercase voice as the "Illustrative render"
 * caption below it. A truck is quoted by measurement here; its loading state can be too.
 *
 * It sits in the middle of the empty frame rather than over the poster, because `BuildViewer`
 * no longer holds a photograph across the load -- so there is no unknown photography to promise
 * contrast against, and the scrim this used to carry went with it.
 *
 * It renders as a sibling of `BuildViewer`'s `role="img"` wrapper, not inside it: children of
 * `role="img"` are presentational to a screen reader, so a `progressbar` nested in one would be
 * announced to nobody.
 */
export function BuildViewerLoading({ progress }: { progress: LoadProgress | null }) {
  const { label, percent } = readoutFor(progress);

  return (
    <div
      data-testid="build-viewer-loading"
      role="progressbar"
      aria-label={label}
      // An indeterminate progressbar is one with no `aria-valuenow` at all, so the attribute is
      // absent rather than zero while the transfer is unmeasurable.
      aria-valuenow={percent ?? undefined}
      aria-valuemin={percent === null ? undefined : 0}
      aria-valuemax={percent === null ? undefined : 100}
      className="pointer-events-none absolute inset-0 flex animate-[viewer-readout-in_600ms_ease-out_both] flex-col items-center justify-center gap-3"
    >
      <p
        aria-hidden="true"
        className="font-data text-ink-muted flex items-baseline gap-3 text-[0.625rem] tracking-[0.2em] uppercase"
      >
        <span>{label}</span>
        {percent === null ? null : <span className="text-accent tabular-nums">{percent}%</span>}
      </p>

      {/* With the sweep suppressed for reduced motion, the segment stays a short bar parked at
          the start of the track. Widening it to fill would read as a finished download rather
          than an unmeasurable one. */}
      <div className="bg-border-strong relative h-px w-48 overflow-hidden sm:w-72">
        {percent === null ? (
          <div className="bg-accent h-full w-[30%] animate-[viewer-readout-sweep_1.4s_linear_infinite] motion-reduce:animate-none" />
        ) : (
          <div
            className="bg-accent h-full transition-[width] duration-300 ease-out motion-reduce:transition-none"
            style={{ width: `${percent}%` }}
          />
        )}
      </div>
    </div>
  );
}
