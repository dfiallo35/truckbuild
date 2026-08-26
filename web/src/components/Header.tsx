"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CTAButton } from "@/components/CTAButton";
import { PRIMARY_NAV, SITE_NAME } from "@/lib/site";

const SCROLL_THRESHOLD = 24;

/**
 * Transparent over hero imagery, gains a solid background once the page scrolls past the hero.
 * Fixed/overlaid by design -- pages that open on a hero should size that hero to clear the
 * header height rather than relying on layout padding here.
 */
export function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > SCROLL_THRESHOLD);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileNavOpen]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled || mobileNavOpen
          ? "border-border bg-canvas/90 border-b backdrop-blur-sm"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6 md:px-10">
        <Link href="/" className="font-display text-ink text-lg tracking-widest uppercase">
          {SITE_NAME}
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {PRIMARY_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="font-data text-ink-muted hover:text-ink text-xs tracking-[0.14em] uppercase"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:block">
          <CTAButton href="/contact">Talk to Sales</CTAButton>
        </div>

        <button
          type="button"
          aria-expanded={mobileNavOpen}
          aria-controls="mobile-nav"
          aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
          onClick={() => setMobileNavOpen((open) => !open)}
          className="text-ink flex h-10 w-10 items-center justify-center md:hidden"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            className="h-6 w-6"
          >
            {mobileNavOpen ? (
              <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
            ) : (
              <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
            )}
          </svg>
        </button>
      </div>

      {mobileNavOpen ? (
        <nav id="mobile-nav" className="border-border bg-canvas border-t px-6 py-6 md:hidden">
          <ul className="flex flex-col gap-5">
            {PRIMARY_NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={() => setMobileNavOpen(false)}
                  className="font-display text-ink text-xl tracking-tight uppercase"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          <CTAButton
            href="/contact"
            className="mt-6 w-full"
            onClick={() => setMobileNavOpen(false)}
          >
            Talk to Sales
          </CTAButton>
        </nav>
      ) : null}
    </header>
  );
}
