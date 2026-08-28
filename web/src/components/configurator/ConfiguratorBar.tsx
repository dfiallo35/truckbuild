import Link from "next/link";

import type { Platform } from "@/lib/contract";
import { SITE_NAME } from "@/lib/site";

/**
 * The configurator's whole chrome: where you are, who to call, and the way out. Everything the
 * marketing header carries -- nav, hero treatment, footer -- would only compete with the build.
 */
export function ConfiguratorBar({ platform }: { platform: Platform }) {
  return (
    <header className="border-border bg-canvas-raised z-30 flex h-14 shrink-0 items-center justify-between gap-4 border-b px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-4">
        <Link
          href="/"
          className="font-display text-ink shrink-0 text-sm tracking-[0.2em] uppercase"
        >
          {SITE_NAME}
        </Link>
        <span className="bg-border hidden h-5 w-px sm:block" />
        <span className="font-data text-ink-muted hidden truncate text-xs tracking-[0.16em] uppercase sm:block">
          {platform.name} — {platform.chassis_basis}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:gap-4">
        <Link
          href="/contact"
          className="font-data text-ink-muted hover:text-accent hidden text-xs tracking-[0.14em] uppercase sm:block"
        >
          Talk to sales
        </Link>
        <Link
          href={`/builds/${platform.slug}`}
          className="font-data text-ink-muted hover:text-ink focus-visible:outline-accent flex items-center gap-2 text-xs tracking-[0.14em] uppercase focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          Exit
          <svg
            viewBox="0 0 24 24"
            aria-hidden
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeWidth={1.5} d="M6 6l12 12M18 6L6 18" />
          </svg>
        </Link>
      </div>
    </header>
  );
}
