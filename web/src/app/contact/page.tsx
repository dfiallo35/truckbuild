import type { Metadata } from "next";

import { ContactForm } from "@/components/ContactForm";
import { SectionHeading } from "@/components/SectionHeading";
import { getCatalog } from "@/lib/catalog";
import { SALES_EMAIL, SALES_PHONE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Talk to TruckBuild sales about a platform, a custom mission, or a build already in progress.",
};

export default async function ContactPage() {
  const catalog = await getCatalog();

  return (
    <section className="py-section px-6 md:px-10">
      <div className="mx-auto grid max-w-6xl gap-16 md:grid-cols-[1.2fr_1fr]">
        <div className="flex flex-col gap-8">
          <SectionHeading
            eyebrow="Get in touch"
            title="Talk to sales"
            description="Tell us the mission and we'll tell you what it takes to build it. No obligation, no auto-generated quote."
          />
          <ContactForm platformOptions={catalog.platforms.map((platform) => platform.name)} />
        </div>

        <div className="border-border flex flex-col gap-6 border-t pt-8 md:border-t-0 md:border-l md:pt-0 md:pl-16">
          <div className="flex flex-col gap-2">
            <span className="font-data text-ink-faint text-xs tracking-[0.14em] uppercase">
              Email
            </span>
            <a href={`mailto:${SALES_EMAIL}`} className="text-ink hover:text-accent text-sm">
              {SALES_EMAIL}
            </a>
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-data text-ink-faint text-xs tracking-[0.14em] uppercase">
              Phone
            </span>
            <a
              href={`tel:${SALES_PHONE.replace(/[^+\d]/g, "")}`}
              className="text-ink hover:text-accent text-sm"
            >
              {SALES_PHONE}
            </a>
          </div>
          <div className="flex flex-col gap-2">
            <span className="font-data text-ink-faint text-xs tracking-[0.14em] uppercase">
              Response time
            </span>
            <p className="text-ink-muted text-sm">One business day, typically less.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
