import type { Metadata } from "next";

import { CTAButton } from "@/components/CTAButton";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";

/**
 * The root 404. It carries the site chrome itself rather than inheriting it, because it also
 * answers for paths outside the `(site)` route group -- a mistyped `/configurator/...` among
 * them -- and those have no header or footer above them to inherit.
 *
 * A dead platform slug lands here, which is the case worth designing for: a build URL shared
 * months ago whose platform has since been renamed. Slugs are public identifiers, so this page
 * points at the current lineup rather than pretending the link never existed.
 */
export const metadata: Metadata = {
  title: "Page not found",
  // A 404 that gets indexed competes with the pages that should be.
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <>
      <Header />
      <main className="flex flex-1 items-center justify-center px-6 py-24">
        <div className="flex max-w-xl flex-col items-center gap-5 text-center">
          <p className="font-data text-ink-faint text-[0.625rem] tracking-[0.2em] uppercase">
            Error 404
          </p>
          <h1 className="font-display text-ink text-4xl tracking-tight uppercase md:text-5xl">
            This page is not in the shop
          </h1>
          <p className="text-ink-muted leading-relaxed">
            The address may be mistyped, or it may point at a build we no longer offer. The current
            platforms are all configurable from the lineup.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
            <CTAButton href="/builds">See the lineup</CTAButton>
            <CTAButton href="/contact" variant="secondary">
              Talk to us
            </CTAButton>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
