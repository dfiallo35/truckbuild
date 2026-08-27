"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import type { Platform } from "@/lib/api";
import { BUILD_PARAM, encodeSelection } from "@/lib/build";
import { formatCents, formatDelta, type PriceBreakdown } from "@/lib/pricing";
import type { RuleViolation } from "@/lib/rules";

/**
 * The whole build in one place, read the way the shop reads a work order: base vehicle, then
 * every line it gains, then what that comes to.
 *
 * A native `<dialog>` rather than a hand-rolled overlay -- Escape, focus trapping and inertness
 * of the page behind it all come with it instead of being approximated.
 */
export function BuildSheet({
  platform,
  selected,
  breakdown,
  violations,
  nameOf,
  onClose,
}: {
  platform: Platform;
  selected: string[];
  breakdown: PriceBreakdown;
  violations: RuleViolation[];
  nameOf: (slug: string) => string;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  const chosen = new Set(selected);
  const lines = platform.option_groups
    .map((group) => ({
      group,
      options: group.options.filter((option) => chosen.has(option.slug)),
    }))
    .filter((line) => line.options.length > 0);

  const query = new URLSearchParams({
    platform: platform.slug,
    [BUILD_PARAM]: encodeSelection(platform, selected),
  });

  return (
    <dialog
      ref={dialog}
      id="build-sheet"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
      aria-labelledby="build-sheet-title"
      className="bg-canvas-raised border-border text-ink m-auto w-[min(40rem,calc(100vw-2rem))] border backdrop:bg-black/70 open:flex open:max-h-[min(44rem,calc(100dvh-2rem))] open:flex-col"
    >
      <div className="border-border flex items-start justify-between gap-4 border-b px-6 py-5">
        <div className="flex flex-col gap-1">
          <span className="font-data text-ink-faint text-[0.625rem] tracking-[0.2em] uppercase">
            Build sheet
          </span>
          <h2 id="build-sheet-title" className="font-display text-xl tracking-tight uppercase">
            {platform.name}
          </h2>
          <p className="text-ink-faint text-xs">{platform.chassis_basis}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close build sheet"
          className="text-ink-muted hover:text-ink focus-visible:outline-accent -m-2 p-2 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeWidth={1.5} d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <dl className="flex flex-col">
          <div className="border-border flex items-baseline justify-between gap-4 border-b py-3">
            <dt className="text-ink-muted text-sm">Base vehicle</dt>
            <dd className="font-data text-ink text-sm tabular-nums">
              {formatCents(breakdown.base_price_cents)}
            </dd>
          </div>

          {lines.map(({ group, options }) => (
            <div key={group.slug} className="border-border border-b py-3">
              <dt className="font-data text-ink-faint mb-2 text-[0.625rem] tracking-[0.18em] uppercase">
                {group.name}
              </dt>
              {options.map((option) => (
                <dd
                  key={option.slug}
                  className="flex items-baseline justify-between gap-4 py-0.5 text-sm"
                >
                  <span className="text-ink-muted">{option.name}</span>
                  <span
                    className={`font-data shrink-0 text-sm tabular-nums ${
                      option.price_delta_cents === 0 ? "text-ink-faint" : "text-ink"
                    }`}
                  >
                    {formatDelta(option.price_delta_cents)}
                  </span>
                </dd>
              ))}
            </div>
          ))}

          <div className="flex items-baseline justify-between gap-4 pt-4">
            <dt className="font-display text-sm tracking-[0.1em] uppercase">Build total</dt>
            <dd className="font-display text-accent text-2xl tabular-nums">
              {formatCents(breakdown.total_cents)}
            </dd>
          </div>
        </dl>

        {violations.length > 0 ? (
          <div className="border-accent/40 bg-accent/5 mt-5 flex flex-col gap-1.5 border-l-2 px-4 py-3">
            <p className="font-data text-accent text-[0.6875rem] tracking-[0.12em] uppercase">
              Resolve before requesting
            </p>
            {violations.map((violation) => (
              <p key={`${violation.kind}-${violation.option}`} className="text-ink text-xs">
                {violation.kind === "requires"
                  ? `${nameOf(violation.option)} needs the ${nameOf(violation.needs!)}.`
                  : `${nameOf(violation.option)} cannot be fitted with the ${nameOf(violation.conflicts_with!)}.`}
              </p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="border-border flex items-center justify-between gap-4 border-t px-6 py-4">
        <p className="text-ink-faint text-xs">
          Pricing is confirmed on order; the final quote is priced by us, not the browser.
        </p>
        {violations.length > 0 ? (
          <button
            type="button"
            disabled
            className="border-border font-display text-ink-faint shrink-0 cursor-not-allowed border px-5 py-2.5 text-xs tracking-[0.1em] uppercase"
          >
            Request this build
          </button>
        ) : (
          <Link
            href={`/contact?${query.toString()}`}
            className="bg-accent text-accent-ink hover:bg-accent-hover focus-visible:outline-accent font-display shrink-0 px-5 py-2.5 text-xs tracking-[0.1em] uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Request this build
          </Link>
        )}
      </div>
    </dialog>
  );
}
