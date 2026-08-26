import type { Metadata } from "next";

import { SectionHeading } from "@/components/SectionHeading";
import { SALES_EMAIL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy policy",
  description:
    "How TruckBuild collects, uses, and protects information submitted through this site.",
};

export default function PrivacyPage() {
  return (
    <section className="py-section px-6 md:px-10">
      <div className="mx-auto flex max-w-3xl flex-col gap-10">
        <SectionHeading eyebrow="Legal" title="Privacy policy" />

        <div className="text-ink-muted flex flex-col gap-8 text-sm leading-relaxed">
          <p>
            Last updated 2026-08-26. This policy covers information collected through
            truckbuild.example — the build configurator, contact and quote forms, and general site
            analytics.
          </p>

          <div className="flex flex-col gap-3">
            <h2 className="font-display text-ink text-lg tracking-tight uppercase">
              What we collect
            </h2>
            <p>
              When you submit a build, a quote request, or the contact form, we collect what you
              enter directly: name, email, phone number, the build configuration, intended use, and
              timeline. We don&rsquo;t collect payment information through this site.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="font-display text-ink text-lg tracking-tight uppercase">
              How we use it
            </h2>
            <p>
              Submitted builds and quote requests go to our sales team to follow up on your inquiry,
              and nowhere else. We don&rsquo;t sell contact information, and we don&rsquo;t use it
              for advertising outside communication about your own inquiry.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="font-display text-ink text-lg tracking-tight uppercase">
              How long we keep it
            </h2>
            <p>
              Quote and contact records are kept for as long as needed to respond to your inquiry
              and maintain a record of the transaction, and are removed on request.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="font-display text-ink text-lg tracking-tight uppercase">Your choices</h2>
            <p>
              To review, correct, or delete information you&rsquo;ve submitted, email{" "}
              <a href={`mailto:${SALES_EMAIL}`} className="text-accent hover:underline">
                {SALES_EMAIL}
              </a>{" "}
              with your request.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
