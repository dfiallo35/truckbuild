import type { Metadata } from "next";

import { CTAButton } from "@/components/CTAButton";
import { ProcessSteps } from "@/components/ProcessSteps";
import { SectionHeading } from "@/components/SectionHeading";

export const metadata: Metadata = {
  title: "Process",
  description: "How a TruckBuild platform goes from consult to a finished, delivered truck.",
};

const STEPS = [
  {
    title: "Consult",
    description:
      "A working session, not a sales pitch. We go through payload, terrain, crew size, and timeline, and tell you straight which platform and options actually fit the job — including if the answer is none of them.",
  },
  {
    title: "Design",
    description:
      "You configure every option group against a live compatibility engine. Incompatible combinations — like a heavy winch without the reinforced bumper it needs — get flagged with a plain explanation, before a single part is ordered.",
  },
  {
    title: "Build",
    description:
      "Chassis arrives at the shop and the upfit begins to the exact spec you configured. Every stage — fabrication, systems, finish — is inspected by the crew accountable for the finished truck, not a separate QA pass at the end.",
  },
  {
    title: "Deliver",
    description:
      "A full walkthrough of every system on the truck, complete documentation for maintenance and warranty, and a build that's ready to work its first day out — not a shakedown period on your dime.",
  },
] as const;

export default function ProcessPage() {
  return (
    <>
      <section className="border-border py-section border-b px-6 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">
          <SectionHeading
            eyebrow="How it works"
            title="Consult to delivery"
            description="Four stages, each one a checkpoint against the last. No surprises between spec and delivery."
          />
        </div>
      </section>

      <section className="px-6 py-16 md:px-10">
        <div className="mx-auto max-w-6xl">
          <ProcessSteps steps={STEPS} />
        </div>
      </section>

      <section className="border-border border-t px-6 py-16 md:px-10">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-8">
          <SectionHeading title="Start with a consult" />
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
