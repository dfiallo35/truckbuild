"use client";

import { useEffect, useRef, useState } from "react";

import { formatCents, formatDelta } from "@/lib/pricing";

const FLASH_MS = 1600;

/**
 * The running total, always in view.
 *
 * The signature moment: a price change shows what it cost the way a shop ticket does -- the
 * delta appears beside the total for a beat, then clears. It is also the visual twin of the
 * announcement the shell sends to assistive technology, so both audiences learn the same thing.
 */
export function PriceBar({
  totalCents,
  optionCount,
  violationCount,
  sheetOpen,
  onToggleSheet,
}: {
  totalCents: number;
  optionCount: number;
  violationCount: number;
  sheetOpen: boolean;
  onToggleSheet: () => void;
}) {
  const previous = useRef(totalCents);
  const [flash, setFlash] = useState<number | null>(null);

  useEffect(() => {
    const delta = totalCents - previous.current;
    previous.current = totalCents;
    if (delta === 0) return;

    setFlash(delta);
    const timer = window.setTimeout(() => setFlash(null), FLASH_MS);
    return () => window.clearTimeout(timer);
  }, [totalCents]);

  return (
    <div className="border-border bg-canvas-raised z-30 flex shrink-0 items-center justify-between gap-4 border-t px-4 py-3 md:px-6">
      <div className="flex min-w-0 items-baseline gap-3 md:gap-5">
        <span className="font-data text-ink-faint hidden text-[0.625rem] tracking-[0.2em] uppercase sm:block">
          Build total
        </span>
        <span
          data-testid="build-total"
          className="font-display text-accent text-xl tabular-nums md:text-2xl"
        >
          {formatCents(totalCents)}
        </span>

        <span
          aria-hidden
          className={`font-data text-ink-muted text-xs tabular-nums transition-opacity duration-500 motion-reduce:transition-none ${
            flash === null ? "opacity-0" : "opacity-100"
          }`}
        >
          {flash === null ? "" : formatDelta(flash)}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-3 md:gap-5">
        {violationCount > 0 ? (
          // A conflict is the one thing worth the space on a narrow screen; the option count
          // is not.
          <span className="font-data text-accent text-[0.6875rem] tracking-[0.12em] uppercase">
            {violationCount} conflict{violationCount === 1 ? "" : "s"}
            <span className="hidden md:inline"> to resolve</span>
          </span>
        ) : (
          <span className="font-data text-ink-faint hidden text-[0.6875rem] tracking-[0.12em] uppercase md:block">
            {optionCount} option{optionCount === 1 ? "" : "s"} selected
          </span>
        )}

        <button
          type="button"
          onClick={onToggleSheet}
          aria-expanded={sheetOpen}
          aria-controls="build-sheet"
          className="bg-accent text-accent-ink hover:bg-accent-hover focus-visible:outline-accent font-display px-5 py-2.5 text-xs tracking-[0.1em] uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {sheetOpen ? "Hide build sheet" : "Review build"}
        </button>
      </div>
    </div>
  );
}
