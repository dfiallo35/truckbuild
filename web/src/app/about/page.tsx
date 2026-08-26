import type { Metadata } from "next";

import { CTAButton } from "@/components/CTAButton";
import { ProofStrip } from "@/components/ProofStrip";
import { SectionHeading } from "@/components/SectionHeading";

export const metadata: Metadata = {
  title: "About",
  description:
    "TruckBuild engineers and fabricates purpose-built truck platforms for expedition, service, and response work.",
};

const STATS = [
  { value: "3", label: "Platforms in production" },
  { value: "18–24 wk", label: "Average build time" },
  { value: "3-yr", label: "Structural warranty" },
  { value: "Lower 48", label: "Delivery coverage" },
] as const;

export default function AboutPage() {
  return (
    <>
      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <SectionHeading
            eyebrow="About TruckBuild"
            title="We build the truck for one job, not every job"
            description="Most upfitters start from a stock chassis and bolt on options until it's close enough. We start from the mission — expedition, service, or response — and engineer the platform around it."
          />
        </div>
      </section>

      <section className="border-border border-b px-6 py-16 md:px-10">
        <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-ink text-xl tracking-tight uppercase">
              Engineered, not assembled
            </h2>
            <p className="text-ink-muted text-sm leading-relaxed">
              Every option in the catalog is checked against every other option before it ever
              reaches a build sheet. If a winch needs a reinforced bumper, the configurator knows
              it. That rigor is what lets us quote a build in minutes instead of weeks of back and
              forth.
            </p>
          </div>
          <div className="flex flex-col gap-4">
            <h2 className="font-display text-ink text-xl tracking-tight uppercase">
              Accountable end to end
            </h2>
            <p className="text-ink-muted text-sm leading-relaxed">
              The same crew that specs your build inspects it at every stage of fabrication.
              There&rsquo;s no separate shop for consult and no separate shop for finish work — one
              team, one truck, start to delivery.
            </p>
          </div>
        </div>
      </section>

      <section className="px-6 py-16 md:px-10">
        <div className="mx-auto max-w-6xl">
          <ProofStrip stats={STATS} />
        </div>
      </section>

      <section className="border-border border-t px-6 py-16 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-8">
          <SectionHeading title="See the platforms" />
          <div className="flex flex-wrap gap-4">
            <CTAButton href="/builds">Browse builds</CTAButton>
            <CTAButton href="/contact" variant="secondary">
              Talk to sales
            </CTAButton>
          </div>
        </div>
      </section>
    </>
  );
}
