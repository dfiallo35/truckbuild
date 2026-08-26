import { cacheLife } from "next/cache";
import Link from "next/link";

import { FOOTER_COLUMNS, SITE_NAME } from "@/lib/site";

async function currentYear(): Promise<number> {
  "use cache";
  cacheLife("days");

  return new Date().getFullYear();
}

export async function Footer() {
  const year = await currentYear();

  return (
    <footer className="border-border bg-canvas-raised border-t">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 md:grid-cols-[1.5fr_1fr_1fr] md:px-10">
        <div className="flex flex-col gap-3">
          <span className="font-display text-ink text-lg tracking-widest uppercase">
            {SITE_NAME}
          </span>
          <p className="text-ink-muted max-w-xs text-sm">
            Purpose-built truck upfits, engineered and configured to order.
          </p>
        </div>

        {FOOTER_COLUMNS.map((column) => (
          <div key={column.heading} className="flex flex-col gap-3">
            <span className="font-data text-ink-faint text-xs tracking-[0.16em] uppercase">
              {column.heading}
            </span>
            <ul className="flex flex-col gap-2">
              {column.links.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-ink-muted hover:text-accent text-sm">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-border border-t px-6 py-6 md:px-10">
        <p className="font-data text-ink-faint text-xs tracking-widest uppercase">
          &copy; {year} {SITE_NAME}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
